"""Pydantic schemas for the Hypothesis Generator (N6) output.

ABTestPlan is the unit of value the whole system produces. Every previous
phase exists to make these high-quality.

Design notes:
  - Each ABTestPlan is SHIPPABLE — has enough info that a person could paste
    it into VWO/Convert/Optimizely without rewriting.
  - The variant has CONCRETE copy/design changes — not "make it better."
  - Each plan ties back to a specific persona + a specific friction.
  - Sample-size hint helps the user / Phase 6 integration know if the test
    is feasible at their traffic volume.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ── Test variants ─────────────────────────────────────────────────────────────

class TestVariant(BaseModel):
    """One concrete page state to test."""
    label: str = Field(..., max_length=80,
                       description="Short label e.g. 'Control', 'Variant A: short headline'")
    description: str = Field(..., max_length=500,
                             description="Plain-English description of what this variant looks like")
    copy_changes: list[str] = Field(
        default_factory=list,
        description=(
            "Specific text changes vs control. Format: 'OLD: <text> → NEW: <text>'. "
            "Each change must be unambiguous (no 'shorten the headline' fluff)."
        ),
    )
    design_changes: list[str] = Field(
        default_factory=list,
        description=(
            "Specific layout/style changes vs control. e.g. 'CTA button moved above fold', "
            "'Trust badge row added between hero and form'."
        ),
    )


# ── Success criteria ─────────────────────────────────────────────────────────

class SuccessCriterion(BaseModel):
    """How to know if the variant won."""
    metric_name: str = Field(..., description="e.g. zip_submit_rate, scroll_depth_50pct, time_on_page")
    direction: Literal["increase", "decrease", "no_change"]
    minimum_detectable_lift_pct: float = Field(
        ..., ge=0.0, le=200.0,
        description="Smallest lift the test should be powered to detect (e.g. 5.0 = 5%)",
    )
    is_primary: bool = Field(False, description="Exactly one criterion should be primary")


# ── Single A/B test plan ──────────────────────────────────────────────────────

TestRiskLevel = Literal["low", "medium", "high"]
ImplementationEffort = Literal["trivial", "low", "medium", "high"]
AwarenessStage = Literal[
    "unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"
]

# ── Test Depth Level (Phase 5d-new) ───────────────────────────────────────────
# This is SCIENTIFIC depth (how many things change), distinct from `risk_level`
# which is IMPLEMENTATION risk.
#
# basic    — 1 element changes (text/color/photo/CTA copy). Clean attribution.
# advanced — 2-4 elements change together (combo). Cannot attribute which drove lift.
# expert   — structural (add/remove sections). Page architecture change.
# super    — fundamental (layout + flow + content paradigm shift).
TestDepthLevel = Literal["basic", "advanced", "expert", "super"]


# Mapping for common aliases the model returns instead of strict Schwartz values.
# Models often confuse the Schwartz stages with UserFlow stages (awareness/
# consideration/intent/action) — we normalize gracefully.
_AWARENESS_ALIASES: dict[str, str] = {
    # Direct Schwartz (case-insensitive copy)
    "unaware": "unaware",
    "problem_aware": "problem_aware",
    "problem-aware": "problem_aware",
    "problemaware": "problem_aware",
    "solution_aware": "solution_aware",
    "solution-aware": "solution_aware",
    "solutionaware": "solution_aware",
    "product_aware": "product_aware",
    "product-aware": "product_aware",
    "productaware": "product_aware",
    "most_aware": "most_aware",
    "most-aware": "most_aware",
    "mostaware": "most_aware",
    # UserFlow stages → closest Schwartz mapping
    "awareness": "problem_aware",
    "consideration": "solution_aware",
    "evaluation": "product_aware",
    "intent": "product_aware",
    "action": "most_aware",
    "post_action": "most_aware",
}


def _normalize_awareness_stage(v: Any) -> Any:
    """Map common aliases to canonical Schwartz value. Pass through if already valid."""
    if not isinstance(v, str):
        return v
    return _AWARENESS_ALIASES.get(v.lower().strip(), v)


class ABTestPlan(BaseModel):
    """One production-ready A/B test plan.

    A reader should be able to: build the variants, set up the test in
    VWO/Convert, hit the right sample size, and call the result — all
    without going back for clarification.
    """

    test_id: str = Field(
        ...,
        description=(
            "Short stable id, format: 'T<seq>-<3-5 word slug>' e.g. 'T1-mobile-form-shortening'. "
            "Generator picks sequential T1, T2, T3..."
        ),
    )

    name: str = Field(..., max_length=160,
                      description="Human-readable test name")

    # The connection to upstream context
    target_persona_name: str = Field(
        ...,
        description=(
            "Which persona this test primarily targets (one of personas[].name from "
            "Customer Insights). Anchors the hypothesis to a real human."
        ),
    )
    addressed_friction: str | None = Field(
        None, max_length=300,
        description=(
            "Which entry from cro.friction_inventory does this test address? "
            "Quote the friction location/issue verbatim if possible. Optional but strong-signal."
        ),
    )
    awareness_stage_targeted: AwarenessStage

    @field_validator("awareness_stage_targeted", mode="before")
    @classmethod
    def _normalize_stage(cls, v: Any) -> Any:
        return _normalize_awareness_stage(v)

    # ── Phase 5d-new: explicit test depth ────────────────────────────────────
    test_depth_level: TestDepthLevel = Field(
        ...,
        description=(
            "basic = 1 element swap (clean attribution). "
            "advanced = 2-4 elements combo. "
            "expert = structural add/remove. "
            "super = paradigm shift."
        ),
    )
    elements_changed: list[str] = Field(
        ..., min_length=1, max_length=10,
        description=(
            "Explicit list of page elements being changed in the variant. "
            "e.g. ['hero_headline'] for basic; "
            "['hero_headline', 'hero_subheadline', 'primary_cta'] for advanced."
        ),
    )
    preservation_notes: str | None = Field(
        None, max_length=400,
        description=(
            "What working elements this test deliberately PRESERVES. "
            "e.g. 'Keeps the trust-badge row, BBB rating, and testimonial — "
            "those are working hard'. Critical for working-page mindset."
        ),
    )

    # The hypothesis itself
    hypothesis_statement: str = Field(
        ..., max_length=800,
        description=(
            "Format: 'Because we observed [X], we believe that [variant] will cause "
            "[metric direction], which we'll know by [success criterion].' "
            "Pre-registered hypothesis — written BEFORE the test starts."
        ),
    )

    # Variants — exactly 2 for A/B (could be 3 for A/B/C in future)
    variants: list[TestVariant] = Field(..., min_length=2, max_length=4)

    # Outcomes
    success_criteria: list[SuccessCriterion] = Field(
        ..., min_length=1, max_length=4,
        description="At least one MUST have is_primary=True.",
    )

    # Calibration
    expected_lift_range_pct: str = Field(
        ..., max_length=300,
        description="Expected lift range with brief justification, e.g. '5-15% (medium-confidence based on form-field reduction history)'",
    )
    risk_level: TestRiskLevel = Field(
        ...,
        description="low=copy-only, medium=layout, high=flow/funnel change",
    )
    implementation_effort: ImplementationEffort = Field(
        ...,
        description="How hard to build the variant — drives test queue prioritization",
    )

    # Estimation
    sample_size_per_arm_estimate: int | None = Field(
        None, ge=100,
        description=(
            "Rough sample size per arm to detect the minimum_detectable_lift at 80% power, "
            "alpha=0.05. Helps user know if traffic volume supports the test."
        ),
    )
    duration_estimate_days: int | None = Field(
        None, ge=1, le=180,
        description="Rough run-time estimate at typical paid-traffic volume",
    )

    # Justification
    rationale: str = Field(
        ..., max_length=1200,
        description=(
            "Why this test is worth running NOW. Reference persona psychology, "
            "channel temperature, observed friction, or copywriting principles. "
            "Avoid 'best practices' — name the specific evidence."
        ),
    )

    rollback_criteria: str = Field(
        default="Variant lifts primary metric by ≥0% and no guardrail metric drops by ≥10%.",
        description="When would we keep the variant vs roll back to control?",
    )

    # ICE for ranking against other plans in the batch
    impact_score: int = Field(..., ge=1, le=10)
    confidence_score: int = Field(..., ge=1, le=10)
    ease_score: int = Field(..., ge=1, le=10)

    @property
    def ice_total(self) -> int:
        return self.impact_score + self.confidence_score + self.ease_score


# ── Generator output (full batch) ────────────────────────────────────────────

class HypothesisGeneratorOutput(BaseModel):
    """The N6 agent's output — a ranked test program, not a single test."""

    plans: list[ABTestPlan] = Field(
        ..., min_length=3, max_length=6,
        description="3-6 A/B test plans ranked by ICE descending.",
    )

    test_program_summary: str = Field(
        ..., max_length=500,
        description=(
            "1-2 sentence executive summary: what is this test program trying to learn / improve "
            "across the 3-6 plans? Used by N7 judge and humans skimming the queue."
        ),
    )

    deferred_ideas: list[str] = Field(
        default_factory=list, max_length=10,
        description=(
            "Test ideas considered but NOT shipped in this batch — kept as a backlog. "
            "Each item: short title + 1-line reason for deferral."
        ),
    )
