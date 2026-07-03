"""Pydantic schemas for Product Director output (Phase 5h)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ShipDecision(BaseModel):
    """One plan being recommended for ship."""
    test_id: str = Field(..., description="From the upstream HG plan")
    ship_order: int = Field(..., ge=1, le=10,
                             description="1 = ship first; 2 = ship after #1 completes; etc.")
    parallel_group: int | None = Field(
        None, ge=1, le=5,
        description="If non-null, plans with same parallel_group ship simultaneously.",
    )
    final_sample_size_per_arm: int | None = Field(
        None, ge=100,
        description="Recommended sample size after Director's MDE check (may differ from HG's estimate).",
    )
    final_duration_days: int | None = Field(
        None, ge=1, le=180,
        description="Director's duration estimate after operating-constraints check.",
    )
    why_this_first: str = Field(
        ..., max_length=400,
        description="1-2 sentence reason for ship_order. Reference learnings expected.",
    )


class IterateDecision(BaseModel):
    """One plan being deferred for revision."""
    test_id: str
    blocker: str = Field(..., max_length=300,
                         description="What specifically blocks ship (e.g. 'sample size insufficient', 'preservation conflict on hero')")
    what_to_fix: list[str] = Field(
        ..., min_length=1, max_length=5,
        description="Concrete fixes for the upstream agent (Generator) to apply on regen.",
    )
    suggested_owner: Literal[
        "hypothesis_generator", "voice_message", "conversion_architect",
        "customer_insights", "media_planner", "audience_strategist",
        "page_works_analyzer", "human_operator",
    ] = Field(..., description="Which agent should act on this iterate decision.")


class KillDecision(BaseModel):
    """One plan being removed from consideration."""
    test_id: str
    kill_reason: str = Field(
        ..., max_length=400,
        description=(
            "Specific reason — must be specific enough to not feel arbitrary. "
            "e.g. 'Repeats March 2026 form-reduction test (4→3 fields, +6% lift confirmed)'."
        ),
    )
    kill_category: Literal[
        "prior_test_repeat",
        "preservation_zone_violation",
        "infeasible_traffic",
        "infeasible_time",
        "constraint_violation",
        "judge_kill_verdict",
        "other",
    ]


class ProductDirectorDecision(BaseModel):
    """Director's full decision package — what the operator reviews."""

    shipped_plans: list[ShipDecision] = Field(
        default_factory=list, max_length=6,
        description="Plans recommended for ship, with sequencing.",
    )
    iterate_plans: list[IterateDecision] = Field(
        default_factory=list, max_length=8,
        description="Plans needing revision before re-consideration.",
    )
    killed_plans: list[KillDecision] = Field(
        default_factory=list, max_length=10,
        description="Plans removed from consideration.",
    )

    strategic_recommendation: str = Field(
        ..., max_length=600,
        description=(
            "2-3 sentences PROGRAM-LEVEL recommendation. NOT test-level "
            "('ship T1') but program-level ('next quarter focus on audience expansion')."
        ),
    )

    constraint_warnings: list[str] = Field(
        default_factory=list, max_length=8,
        description=(
            "Explicit notes on operating constraints the operator should know about. "
            "e.g. 'baseline_conversion_rate_pct missing — sample size estimates are best-guess'."
        ),
    )

    expert_conflicts_resolved: list[str] = Field(
        default_factory=list, max_length=6,
        description=(
            "Log of where Director overruled an expert. "
            "e.g. 'HG proposed hero rewrite (T2); Page-Works said preserve. Director sided with Page-Works.'"
        ),
    )

    next_batch_focus: str | None = Field(
        None, max_length=400,
        description=(
            "Optional: what the NEXT test batch should focus on, given what this batch will teach."
        ),
    )

    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="0.0-1.0 overall confidence. Drops when constraints missing, expert outputs incomplete, or conflicts unresolved.",
    )
