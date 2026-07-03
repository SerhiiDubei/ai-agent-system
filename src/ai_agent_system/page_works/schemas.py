"""Pydantic schemas for Page-Works Analyzer output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


BaselineAssessment = Literal["works", "partial", "broken", "unknown"]


class LiftScoring(BaseModel):
    """Per-lever scoring (1-5) on the LIFT model, applied in REVERSE — high score = preserve.

    5 = lever is doing heavy lifting, do not touch.
    4 = lever is solid, can test variants but expect small wins.
    3 = lever is adequate, change-safe zone.
    2 = lever is weak, reasonable test target.
    1 = lever is broken, priority test target.
    """
    value_proposition: int = Field(..., ge=1, le=5)
    relevance: int = Field(..., ge=1, le=5)
    clarity: int = Field(..., ge=1, le=5)
    anxiety_management: int = Field(..., ge=1, le=5)
    distraction: int = Field(..., ge=1, le=5,
                              description="5 = LOW distraction (one CTA path); 1 = HIGH distraction")
    urgency: int = Field(..., ge=1, le=5)

    rationale_per_high_lever: dict[str, str] = Field(
        default_factory=dict,
        description="For levers scoring 4-5, name WHY it's working. Key=lever, value=rationale.",
    )


class TrustMechanism(BaseModel):
    """One trust signal on the page with estimated conversion-load share."""
    element: str = Field(..., description="Specific element, e.g. 'BBB A+ badge above-fold'")
    estimated_load_pct: int = Field(..., ge=0, le=100,
                                     description="Rough estimate of % of conversion work this element does.")
    why_working: str = Field(..., max_length=300,
                              description="One sentence: WHY this is working for this audience.")


class PageElement(BaseModel):
    """A page element classified into preservation or change-safe."""
    element: str = Field(..., description="Specific element name, e.g. 'hero_headline', 'phone_number_above_fold'")
    reason: str = Field(..., max_length=400,
                         description="Why preserved or change-safe. Must be specific.")


class PageWorksAnalysis(BaseModel):
    """Full output of Page-Works Analyzer for one LP audit."""

    baseline_assessment: BaselineAssessment = Field(
        ...,
        description="Holistic verdict on whether the page is currently working.",
    )

    lift_scoring: LiftScoring

    trust_anatomy: list[TrustMechanism] = Field(
        ..., min_length=2, max_length=8,
        description="Top 3-5 trust mechanisms with load-share estimates.",
    )

    preservation_zones: list[PageElement] = Field(
        ..., min_length=1, max_length=12,
        description=(
            "Page elements that are LOAD-BEARING. Downstream agents must justify "
            "any test here with extraordinary evidence."
        ),
    )

    change_safe_zones: list[PageElement] = Field(
        default_factory=list, max_length=12,
        description=(
            "Page elements safe to test variants on with normal evidence. "
            "Does NOT mean 'should change' — just 'safer to test'."
        ),
    )

    warnings_for_downstream: list[str] = Field(
        ..., min_length=1, max_length=10,
        description=(
            "Explicit, actionable warnings to other agents. Each must reference "
            "a specific decision space (e.g. 'DO NOT propose hero_headline rewrite'). "
            "Vague warnings are forbidden."
        ),
    )

    working_mechanisms_summary: str = Field(
        ..., max_length=600,
        description=(
            "1-2 paragraphs synthesizing WHY this page is working. The 'archaeologist's "
            "report' that downstream agents read first."
        ),
    )

    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description=(
            "0.0-1.0 confidence in the analysis. Drops when page_context is incomplete "
            "or operating_constraints.baseline_conversion_rate_pct is missing."
        ),
    )
