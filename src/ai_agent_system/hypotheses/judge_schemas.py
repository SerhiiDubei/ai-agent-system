"""Pydantic schemas for the Hypothesis Judge (N7) output.

Judge consumes a HypothesisGeneratorOutput and produces structured critiques
+ ship/iterate/kill verdicts per plan.

Design notes:
  - Judge is OPTIMIZED for skeptical evaluation, not creative production.
  - Verdict triad (ship / iterate / kill) is intentional — forces decision,
    discourages "this is fine" middle-ground review fatigue.
  - Per-dimension scoring (1-10) lets future N7-v2 auto-regenerate just the
    weak dimensions of a plan instead of regenerating the whole batch.
  - The Judge does NOT modify plans — only assesses. Modification belongs
    to the Generator (or a future "PlanRevisor" agent).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


JudgeVerdictType = Literal["ship", "iterate", "kill"]


class JudgeVerdict(BaseModel):
    """One judge assessment of one ABTestPlan."""

    test_id: str = Field(
        ...,
        description="Must match an ABTestPlan.test_id from the input batch (e.g. 'T1-mobile-form-shortening').",
    )

    verdict: JudgeVerdictType = Field(
        ...,
        description=(
            "ship   = plan is shippable as-is, no rewrite needed. "
            "iterate = plan has fixable issues — return to Generator with weaknesses. "
            "kill   = plan should not be in the program — wrong test, bad evidence."
        ),
    )

    overall_score: int = Field(
        ..., ge=1, le=10,
        description="1-10 holistic quality. ≥8 = ship; 5-7 = iterate; ≤4 = kill.",
    )

    # Per-dimension scores — useful for v2 auto-regeneration of weak parts only
    hypothesis_quality_score: int = Field(
        ..., ge=1, le=10,
        description="Does hypothesis follow Because/We believe/We'll know format with concrete bracket-fill?",
    )
    variant_concreteness_score: int = Field(
        ..., ge=1, le=10,
        description="Are copy_changes / design_changes specific enough that a developer could implement without questions?",
    )
    persona_anchor_score: int = Field(
        ..., ge=1, le=10,
        description="Does the plan tie to a real persona's psychology / pain / awareness stage, not just say its name?",
    )
    friction_grounding_score: int = Field(
        ..., ge=1, le=10,
        description="Does the test address a documented friction (CRO inventory or page_context observation)?",
    )
    sample_size_realism_score: int = Field(
        ..., ge=1, le=10,
        description="Is sample_size_per_arm_estimate calibrated to the expected_lift_range_pct?",
    )
    ice_defensibility_score: int = Field(
        ..., ge=1, le=10,
        description="Are I/C/E scores consistent with the evidence the plan provides?",
    )

    strengths: list[str] = Field(
        ..., min_length=1, max_length=4,
        description="1-4 specific things this plan did well. Cite the exact field/element.",
    )
    weaknesses: list[str] = Field(
        default_factory=list, max_length=6,
        description=(
            "1-6 specific issues. Each must be actionable — not 'unclear', "
            "but 'hypothesis_statement does not name the success criterion'."
        ),
    )
    suggested_improvements: list[str] = Field(
        default_factory=list, max_length=6,
        description=(
            "1-6 concrete revisions. Map 1-1 to weaknesses where possible. "
            "Example: 'Tighten variant copy: replace \"better headline\" with verbatim text.'"
        ),
    )


class HypothesisJudgeOutput(BaseModel):
    """Judge's full assessment of a hypothesis batch."""

    verdicts: list[JudgeVerdict] = Field(
        ..., min_length=1,
        description="One verdict per plan in the input batch. Order matches input.",
    )

    program_assessment: str = Field(
        ..., max_length=600,
        description=(
            "1-2 sentence verdict on the WHOLE batch. e.g. 'Solid program — 2 ship, "
            "1 iterate. Strong friction grounding. Weakness: all tests target the "
            "primary persona; consider one test for the decision_helper.'"
        ),
    )

    ship_count: int = Field(..., ge=0, description="How many plans got 'ship' verdict")
    iterate_count: int = Field(..., ge=0, description="How many got 'iterate'")
    kill_count: int = Field(..., ge=0, description="How many got 'kill'")

    cross_plan_observations: list[str] = Field(
        default_factory=list, max_length=5,
        description=(
            "Observations across the whole batch that no single-plan verdict captures. "
            "e.g. 'All 3 plans target Sarasota Helen — decision_helper persona ignored.' "
            "Or: 'No big-rock test (Impact >= 7) in the batch.'"
        ),
    )
