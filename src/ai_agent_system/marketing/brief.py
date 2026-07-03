"""MarketingBrief — input schema for the decomposed drafter pipeline.

Single, immutable input that gets passed (or sliced) to every sub-agent.
Sub-agents see this verbatim — they do NOT see each other's outputs except
where the orchestrator explicitly threads them in (e.g. VoiceMessage gets
the personas from CustomerInsights).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from typing import Literal

from ai_agent_system.marketing.models import (
    PageGoal,
    TrafficSource,
)


# ── Operating constraints — first-class input that drives test strategy ──────

RiskAppetite = Literal["conservative", "balanced", "experimental"]


class OperatingConstraints(BaseModel):
    """Real-world constraints that drive test design strategy.

    Phase 5d-new — these are NOT "limits applied after ideas." They are
    PRIMARY DATA that dictates which ideas can be generated AT ALL.

    Examples:
      - 10k traffic + 19-21% baseline + 2-4% expected lift → ONLY basic tests
        (MDE math forbids smaller changes)
      - 50k traffic + low baseline → can run 1 super test "where to go" + basics
      - 500k traffic → expert/super tests routine
    """

    monthly_traffic_volume: int | None = Field(
        None, ge=100,
        description="Visitors/month to the LP. Used for MDE calculations.",
    )
    baseline_conversion_rate_pct: float | None = Field(
        None, ge=0.0, le=100.0,
        description="Current conversion rate (e.g. 19.5). Required for sample-size math.",
    )
    time_window_days: int | None = Field(
        None, ge=1, le=365,
        description="How long the test program can run (e.g. 7 = 1 week sprint).",
    )
    expected_lift_floor_pct: float | None = Field(
        None, ge=0.0, le=200.0,
        description=(
            "Smallest relative lift the operator wants to detect. e.g. 4.0 = 4% rel lift. "
            "Drives what test depth is feasible."
        ),
    )
    risk_appetite: RiskAppetite = Field(
        "balanced",
        description=(
            "conservative = basic-only, predictable wins. "
            "balanced = mix of basic + advanced. "
            "experimental = include 1+ super test for direction-finding."
        ),
    )

    # ── BUDGET (Phase 5d.1 — money math, not just traffic math) ──────────────
    total_program_budget_usd: float | None = Field(
        None, ge=0.0,
        description=(
            "Total ad-spend budget for the test program window. "
            "Director uses this for ROI feasibility (cost of running each variant)."
        ),
    )
    target_cpa_usd: float | None = Field(
        None, ge=0.0,
        description=(
            "Target cost-per-acquisition. If a test's variant lifts CPA above this, "
            "Director flags as economically infeasible regardless of conversion lift."
        ),
    )
    current_cpa_usd: float | None = Field(
        None, ge=0.0,
        description=(
            "Current cost-per-acquisition (pre-test baseline). "
            "Lets Director compute relative ROI improvement, not just absolute."
        ),
    )

    prior_tests_tried: list[str] = Field(
        default_factory=list, max_length=50,
        description=(
            "Short descriptions of tests already attempted (so we don't repeat). "
            "Format: 'short description + outcome'. e.g. 'Reduced form 4→3 fields, +6% in March 2026'."
        ),
    )
    additional_notes: str | None = Field(
        None, max_length=1000,
        description="Free-text any other operational context the operator wants to share.",
    )


# ── Current Performance — real analytics data from operator (Phase 5d.1) ─────

class FunnelStep(BaseModel):
    """One step in the conversion funnel with measured drop-off."""
    name: str = Field(..., description="e.g. 'page_view', 'form_start', 'step_1', 'submit'")
    visitors_entering: int = Field(..., ge=0)
    visitors_continuing: int = Field(..., ge=0,
                                      description="Visitors who completed THIS step")
    completion_rate_pct: float = Field(..., ge=0.0, le=100.0)
    median_time_seconds: int | None = Field(
        None, ge=0,
        description="Median time spent on this step (UX diagnostic)",
    )


class CurrentPerformance(BaseModel):
    """Real performance metrics from operator's analytics — replaces guesses with data.

    Every field optional. When provided, Director + Page-Works use these to
    sharpen analysis. Without them, the system falls back to baseline-only math.

    Common sources: GA4, Hotjar, FullStory, Triple Whale, Northbeam, Meta Ads,
    Google Ads dashboards, the operator's own spreadsheet.
    """

    # ── Acquisition (ad-side metrics) ────────────────────────────────────────
    monthly_impressions: int | None = Field(None, ge=0)
    monthly_clicks: int | None = Field(None, ge=0)
    ctr_pct: float | None = Field(
        None, ge=0.0, le=100.0,
        description="Click-through rate from ad to LP (clicks / impressions × 100).",
    )
    cpc_usd: float | None = Field(None, ge=0.0,
                                   description="Cost per click (ad spend / clicks).")
    cpm_usd: float | None = Field(None, ge=0.0,
                                   description="Cost per mille (per 1000 impressions).")

    # ── Page-side engagement ─────────────────────────────────────────────────
    bounce_rate_pct: float | None = Field(None, ge=0.0, le=100.0)
    median_time_on_page_seconds: int | None = Field(None, ge=0)
    scroll_depth_50_pct: float | None = Field(
        None, ge=0.0, le=100.0,
        description="% of users who scroll past 50% of the page.",
    )
    scroll_depth_75_pct: float | None = Field(None, ge=0.0, le=100.0)

    # ── Conversion (with viewport split where available) ─────────────────────
    overall_conversion_rate_pct: float | None = Field(
        None, ge=0.0, le=100.0,
        description="Combined CR across all viewports. If split known, prefer mobile/desktop.",
    )
    mobile_conversion_rate_pct: float | None = Field(None, ge=0.0, le=100.0)
    desktop_conversion_rate_pct: float | None = Field(None, ge=0.0, le=100.0)
    monthly_conversions: int | None = Field(None, ge=0)

    # ── Form-specific (when applicable) ──────────────────────────────────────
    form_start_rate_pct: float | None = Field(
        None, ge=0.0, le=100.0,
        description="% of LP visitors who start the form (any field touched).",
    )
    form_completion_rate_pct: float | None = Field(
        None, ge=0.0, le=100.0,
        description="% of form-starters who submit. Tells Director if drop-off is at form vs at page.",
    )

    # ── Money / unit economics ───────────────────────────────────────────────
    cpl_usd: float | None = Field(None, ge=0.0,
                                   description="Cost per lead (ad spend / conversions).")
    roas: float | None = Field(
        None, ge=0.0,
        description="Return on ad spend (revenue generated / ad spend).",
    )
    aov_usd: float | None = Field(None, ge=0.0,
                                   description="Average order value (for ecom).")
    ltv_usd: float | None = Field(
        None, ge=0.0,
        description="Lifetime value of converted customer. Drives true ROAS calculation.",
    )

    # ── Funnel diagnostics (when operator has step-level analytics) ──────────
    funnel_steps: list[FunnelStep] = Field(
        default_factory=list, max_length=12,
        description=(
            "Per-step funnel data. When provided, Director knows EXACTLY where "
            "users drop off — no need to guess at friction points."
        ),
    )
    biggest_dropoff_step_name: str | None = Field(
        None,
        description="Name of the step with the largest absolute drop-off (operator-specified).",
    )

    # ── Free-text observations ───────────────────────────────────────────────
    operator_notes: str | None = Field(
        None, max_length=1500,
        description=(
            "Anything else the operator observed (e.g. 'mobile users abandon at "
            "phone-field; desktop users skim past trust badges')."
        ),
    )


class MarketingBrief(BaseModel):
    """User input to the decomposed drafter."""

    # Project identity
    niche: str = Field(..., description="e.g. walk_in_tubs, debt_relief, hearing_aids")
    parent_category: str = Field(..., description="e.g. home_safety, financial_services")

    # Market
    market: str = Field(..., description="e.g. US-FL, US, GB, CA")
    language: str = Field(..., pattern=r"^[a-z]{2}(-[A-Z]{2})?$",
                          description="ISO e.g. 'en' or 'en-US'")

    # Traffic & goal
    traffic_source_primary: TrafficSource
    page_goal: PageGoal
    primary_metric: str = Field(..., description="e.g. zip_submit_rate, cost_per_lead")

    # Free-text brief
    brief: str = Field(..., description="The marketer's verbal brief — fuzzy is OK")

    # Optional constraints
    business_constraints: str | None = Field(
        None,
        description="Special Ad Categories, regulatory limits, brand restrictions",
    )

    # Operating reality (Phase 5d-new — first-class input, not afterthought)
    operating_constraints: OperatingConstraints | None = Field(
        None,
        description="Traffic volume, baseline conversion, time window, prior tests, risk appetite, BUDGET",
    )

    # Real performance metrics (Phase 5d.1 — when operator has real analytics)
    current_performance: CurrentPerformance | None = Field(
        None,
        description=(
            "Real CTR/CR/ROAS/funnel data from operator's analytics. Every field "
            "optional but each one sharpens Director + Page-Works analysis when present."
        ),
    )

    # Optional client identity (Phase 5g — persistent state per client)
    client_id: str | None = Field(
        None, max_length=64,
        description=(
            "Stable client identifier for persistent expert state. "
            "Same client across runs → experts read/write to agents/<expert>/state/<client_id>/."
        ),
    )

    # Optional captured page data (populated in Phase 2 from snapshot system)
    page_snapshot_id: int | None = Field(
        None,
        description="DB id of a captured snapshot (Phase 2 integration)",
    )
