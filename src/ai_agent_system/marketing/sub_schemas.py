"""Sub-output schemas — one per specialized agent.

Each agent in the decomposed drafter pipeline produces its OWN small
schema (5-15 fields), not the full MarketingContext. The Assembler
later flattens these into a single MarketingContext.

Why small schemas:
  - Lower validation pressure (fewer fields = fewer ways to fail)
  - Faster generation (model writes less)
  - Cleaner agent boundaries (each agent has one job)
  - Reusable: hypothesis-generator agents can consume specific sub-schemas
    without needing the whole context

Naming convention:
  <AgentName>Output  — what the agent returns
  e.g. CustomerInsightsOutput, VoiceMessageOutput

NEW types introduced here (not in legacy models.py):
  - HeadlineAngle, TestPriority, FrictionPoint
  - VoiceMessageOutput is the biggest gap-fill: legacy schema had no
    structured copy/message fields at all.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ai_agent_system.marketing.models import (
    AudienceProfile,
    ChannelProfile,
    PainPoint,
    Persona,
    UserFlow,
)


# ── Customer Insights Strategist ──────────────────────────────────────────────

class CustomerInsightsOutput(BaseModel):
    """Owned by the Customer Insights Strategist agent.

    Builds the human side of the brief: who they are, what they're trying
    to do, what hurts. Downstream agents consume `personas` for everything
    targeting/copy/flow related.
    """
    personas: list[Persona] = Field(
        ..., min_length=3, max_length=5,
        description="3-5 sharp, niche-specific personas with JTBD and pain triggers.",
    )
    pain_points_aggregate: list[PainPoint] = Field(
        ..., min_length=3,
        description=(
            "Top pain points across all personas, deduplicated. "
            "These are the pains the LP must directly address above the fold."
        ),
    )
    audience_psychology_summary: str = Field(
        ...,
        description=(
            "1-2 paragraph synthesis: what is the dominant emotion driving this "
            "audience to seek a solution NOW? What are they really afraid of? "
            "Used by Voice & Message Strategist as raw material for copy."
        ),
    )


# ── Voice & Message Strategist ────────────────────────────────────────────────

class HeadlineAngle(BaseModel):
    """One angle the page could lead with."""
    angle_name: str = Field(..., description="Short label e.g. 'fear-of-falling', 'aging-in-place freedom'")
    awareness_stage: Literal[
        "unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"
    ] = Field(..., description="Schwartz awareness stage this angle targets")
    sample_headline: str = Field(
        ..., max_length=120,
        description="Concrete headline written in the persona's voice, ≤120 chars",
    )
    rationale: str = Field(
        ..., max_length=200,
        description="Why this angle works — psychology + audience evidence",
    )


class VoiceMessageOutput(BaseModel):
    """Owned by the Voice & Message Strategist (Conversion Copywriter).

    The most important agent for actual A/B test ROI: copy beats design
    on conversion lift in 80% of LP tests. This agent extracts message
    angles, banned cliches, and verbatim customer voice.
    """
    primary_value_prop: str = Field(
        ..., max_length=200,
        description=(
            "ONE clear value prop, fits on a t-shirt. NOT a feature list, "
            "NOT a slogan. Format hint: 'I help [audience] [achieve outcome] "
            "without [common pain].'"
        ),
    )
    hook_variations: list[str] = Field(
        ..., min_length=3, max_length=5,
        description=(
            "3-5 ad-creative hooks (first-2-seconds line for paid social). "
            "Each ≤80 chars. Mix awareness stages."
        ),
    )
    headline_angles: list[HeadlineAngle] = Field(
        ..., min_length=3, max_length=5,
        description="3-5 distinct angles for above-the-fold LP headline tests.",
    )
    banned_words: list[str] = Field(
        default_factory=list,
        description=(
            "Cliches to forbid in generated copy. Default: revolutionary, unlock, "
            "leverage, seamless, game-changing, world-class, cutting-edge."
        ),
    )
    voice_examples: list[str] = Field(
        ..., min_length=2, max_length=6,
        description=(
            "Verbatim customer language (or plausible reconstruction if no real "
            "reviews). Used by hypothesis-gen to write copy that sounds like the "
            "user, not the brand."
        ),
    )


# ── Media Planner ─────────────────────────────────────────────────────────────

class MediaPlanOutput(BaseModel):
    """Owned by the Media Planner agent.

    Defines the channel context the LP lives inside. Discriminator-aware
    via ChannelProfile so each channel gets its own strict sub-fields.
    """
    channel_profile: ChannelProfile = Field(
        ...,
        description=(
            "Channel-specific mechanics. .channel field MUST equal the brief's "
            "traffic_source_primary (assembler validates)."
        ),
    )
    channel_temperature: Literal["cold", "warm", "hot"] = Field(
        ...,
        description=(
            "How interrupt-y is the audience in this channel? "
            "cold=Meta scroll-interrupt, warm=Display/YouTube intent signals, "
            "hot=Google Search transactional. Drives copy register and proof intensity."
        ),
    )
    creative_grammar: str = Field(
        ..., max_length=500,
        description=(
            "Brief on how creative SHOULD feel in this channel: pace, tone, "
            "production quality, hook style. e.g. for TikTok: 'lo-fi UGC, "
            "no logo in first 1.5s, hook = pattern interrupt'."
        ),
    )


# ── Audience Strategist ───────────────────────────────────────────────────────

class AudienceSegmentationOutput(BaseModel):
    """Owned by the Audience Strategist agent.

    Translates personas into actionable targeting recipes (who to clone,
    who to exclude, what behaviour signals predict conversion).
    """
    audience_profile: AudienceProfile = Field(
        ...,
        description=(
            "Primary persona name MUST match one persona produced by Customer "
            "Insights (assembler validates this cross-field constraint)."
        ),
    )
    lookalike_seeds: list[str] = Field(
        ..., min_length=2, max_length=5,
        description=(
            "Concrete seed audiences for Meta/Google lookalikes. Real, usable "
            "signals — NOT 'people interested in home improvement'. "
            "Examples: 'past-90-day buyers of mobility aids', 'AARP members in FL', "
            "'video-watchers >75% on caregiver content'."
        ),
    )
    exclusion_signals: list[str] = Field(
        default_factory=list, max_length=5,
        description=(
            "Who to EXCLUDE — wrong-fit signals that waste budget. "
            "e.g. 'Engagement: contractors / installers' (B2B noise), "
            "'Past converters in last 14d' (already bought)."
        ),
    )


# ── Conversion Architect (CRO Lead) ───────────────────────────────────────────

class TestPriority(BaseModel):
    """One A/B test idea ranked by ICE."""
    element: str = Field(..., description="Page element to test e.g. 'hero headline', 'CTA copy'")
    hypothesis: str = Field(..., max_length=300, description="What you predict will happen and why")
    impact_score: int = Field(..., ge=1, le=10, description="1-10, expected lift size")
    confidence_score: int = Field(..., ge=1, le=10, description="1-10, evidence strength")
    ease_score: int = Field(..., ge=1, le=10, description="1-10, implementation effort (10=trivial)")

    @property
    def ice_total(self) -> int:
        return self.impact_score + self.confidence_score + self.ease_score


class FrictionPoint(BaseModel):
    """Known LP friction the architect spotted from the brief / page."""
    location: str = Field(..., description="Where on the page (above-fold, form, footer, etc.)")
    issue: str = Field(..., max_length=200, description="What hurts conversion")
    severity: Literal["low", "medium", "high", "critical"]


class ConversionArchitectureOutput(BaseModel):
    """Owned by the Conversion Architect (CRO Lead) agent.

    Designs the funnel logic and test priorities. Driven by LIFT model
    (Value/Relevance/Clarity/Anxiety/Distraction/Urgency) — NOT by best
    practices, which are usually wrong for the specific audience.
    """
    user_flow: UserFlow = Field(
        ...,
        description="Stage-by-stage user journey through the LP (3-7 stages).",
    )
    test_priorities: list[TestPriority] = Field(
        ..., min_length=3, max_length=8,
        description=(
            "Top A/B test ideas ranked by ICE. Each must be a CONCRETE element "
            "+ hypothesis. NO 'test the colors' style fluff."
        ),
    )
    friction_inventory: list[FrictionPoint] = Field(
        default_factory=list, max_length=10,
        description=(
            "Known/likely friction points. If LP not yet captured, use brief + "
            "page_goal to predict what will hurt conversion (e.g. 'phone field "
            "before email = 30% drop on mobile')."
        ),
    )

    @model_validator(mode="after")
    def _ice_sanity(self) -> "ConversionArchitectureOutput":
        """At least one test should have ICE ≥ 18 (worth running)."""
        if self.test_priorities and not any(t.ice_total >= 18 for t in self.test_priorities):
            # Soft warning — not a validation failure. CRO Lead might genuinely
            # think nothing is high-ICE for this brief.
            pass
        return self
