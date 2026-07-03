#!/usr/bin/env python
"""E2E test of Pipeline v3 with FULL real-data brief (Phase 5d.1).

Tests the new budget + CurrentPerformance integration:
  - operating_constraints.total_program_budget_usd / target_cpa_usd / current_cpa_usd
  - current_performance: CTR/CR/ROAS/funnel_steps/operator_notes/etc.

Director should now use ROI math in addition to MDE math, and reference
specific real numbers in strategic_recommendation.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_agent_system.marketing.brief import (
    CurrentPerformance,
    FunnelStep,
    MarketingBrief,
    OperatingConstraints,
)
from ai_agent_system.marketing.full_pipeline_v3 import run_full_pipeline_v3
from ai_agent_system.marketing.page_context import PageContext


# ── Real-data brief (homeiq.io with realistic operator analytics) ────────────

BRIEF = MarketingBrief(
    niche="walk_in_tubs",
    parent_category="home_safety",
    market="US-FL",
    language="en",
    traffic_source_primary="meta",
    page_goal="zip_submit",
    primary_metric="zip_submit_rate",
    brief=(
        "HomeIQ sells walk-in tubs and bath safety solutions for seniors. "
        "Target: 65+ adults in Florida who fear falling in the shower or tub, "
        "plus adult children helping aging parents. Traffic: Meta paid ads. "
        "Goal: ZIP code submission. Free in-home assessment, no high-pressure sales."
    ),
    business_constraints="Special Ad Category: housing — age/ZIP targeting blocked.",
    client_id="homeiq_io_realdata",

    # ── Operating constraints WITH BUDGET ───────────────────────────────────
    operating_constraints=OperatingConstraints(
        monthly_traffic_volume=12000,
        baseline_conversion_rate_pct=21.3,
        time_window_days=14,
        expected_lift_floor_pct=4.0,
        risk_appetite="balanced",
        # NEW — budget fields
        total_program_budget_usd=2500.0,
        target_cpa_usd=18.0,
        current_cpa_usd=22.50,
        prior_tests_tried=[
            "Reduced form fields 4→3, +6.2% in March 2026",
            "Hero subheadline tweak, no significant lift in April 2026",
        ],
        additional_notes=(
            "Operator's lead-quality is high — form is filtering effectively. "
            "Don't propose further form-field reduction without lead-quality evidence."
        ),
    ),

    # ── NEW: real performance metrics ───────────────────────────────────────
    current_performance=CurrentPerformance(
        # Acquisition
        monthly_impressions=580_000,
        monthly_clicks=12_000,
        ctr_pct=2.07,
        cpc_usd=1.45,
        cpm_usd=29.97,
        # Engagement (mobile is weaker — visible signal)
        bounce_rate_pct=42.0,
        median_time_on_page_seconds=87,
        scroll_depth_50_pct=68.0,
        scroll_depth_75_pct=44.0,
        # Conversion (mobile vs desktop split — KEY INSIGHT)
        overall_conversion_rate_pct=21.3,
        mobile_conversion_rate_pct=12.4,    # 2.3× lower than desktop!
        desktop_conversion_rate_pct=28.7,
        monthly_conversions=2556,
        # Form-specific (page loss > form loss → fix the page first)
        form_start_rate_pct=38.0,           # only 38% of visitors engage form
        form_completion_rate_pct=56.0,      # of starters, 56% complete
        # Money
        cpl_usd=22.50,
        roas=2.8,
        aov_usd=63.0,
        # Funnel steps
        funnel_steps=[
            FunnelStep(name="page_view", visitors_entering=12000,
                       visitors_continuing=6960, completion_rate_pct=58.0,
                       median_time_seconds=87),
            FunnelStep(name="form_start", visitors_entering=6960,
                       visitors_continuing=4560, completion_rate_pct=65.5,
                       median_time_seconds=24),
            FunnelStep(name="submit", visitors_entering=4560,
                       visitors_continuing=2556, completion_rate_pct=56.1),
        ],
        biggest_dropoff_step_name="page_view",
        operator_notes=(
            "Mobile bounce is 58% vs desktop 31% — 2x worse. "
            "Suspect (a) page-load on mobile is slow, (b) hero headline is too long for mobile scan-time. "
            "Calls have been picking up after form submit, lead-quality is strong."
        ),
    ),
)


MOCK_PAGE = PageContext(
    snapshot_id=999_001,
    viewport_used="desktop",
    url="https://homeiq.io/walkintubs",
    title="Walk-In Tubs for Seniors | Free In-Home Assessment | HomeIQ",
    meta_description=(
        "Premium walk-in tubs designed for safety and comfort. Free in-home "
        "assessment from local installers. Veteran discounts available."
    ),
    page_archetype="lead_capture",
    archetype_confidence=0.92,
    detected_element_roles=[
        "hero_headline", "hero_subheadline", "primary_cta",
        "lead_form", "trust_badge", "testimonial",
    ],
    forms_summary=[
        "desktop form: 4 fields (zip, name, email, phone) — submit='Get My Free Assessment'",
        "mobile form: 4 fields (zip, name, email, phone) — submit='Get Started'",
    ],
    friction_signals=[
        "Mobile form has 4 fields — typical drop-off ~10-20% above 3 fields",
        "No visible phone number / click-to-call detected",
        "Hero headline length ~14 words may exceed scan-time on mobile",
    ],
    tech_stack=["WordPress", "Elementor", "Google Tag Manager", "Meta Pixel"],
    visible_copy_excerpt=(
        "# Stay Safe and Independent at Home with Premium Walk-In Tubs\n\n"
        "Discover the best walk-in tubs designed for seniors, offering safety, "
        "comfort, and ease of use. Get a free in-home assessment from a local "
        "installer today.\n\n"
        "## Why Choose HomeIQ?\n\n"
        "- 4,500+ Florida seniors served\n"
        "- BBB A+ Accredited Business\n"
        "- Established 2009\n"
        "- Veteran and military discounts\n"
        "- No high-pressure sales tactics\n\n"
        '"After my fall last year, my daughter insisted I get a walk-in tub. '
        'HomeIQ made the whole process easy and the installer was wonderful." '
        "— Margaret, 74, Sarasota FL"
    ),
)


async def main() -> int:
    print("=" * 95)
    print("PIPELINE V3 — REAL-DATA TEST (Phase 5d.1)")
    print("=" * 95)
    print(f"\nclient_id: {BRIEF.client_id}")
    print(f"niche: {BRIEF.niche}")
    print()
    print("OPERATING CONSTRAINTS:")
    print(f"  traffic={BRIEF.operating_constraints.monthly_traffic_volume:,}/mo "
          f"baseline={BRIEF.operating_constraints.baseline_conversion_rate_pct}% "
          f"window={BRIEF.operating_constraints.time_window_days}d")
    print(f"  budget=${BRIEF.operating_constraints.total_program_budget_usd:,.0f} "
          f"target_cpa=${BRIEF.operating_constraints.target_cpa_usd} "
          f"current_cpa=${BRIEF.operating_constraints.current_cpa_usd}")
    print()
    print("CURRENT PERFORMANCE:")
    cp = BRIEF.current_performance
    print(f"  ctr={cp.ctr_pct}%  cpc=${cp.cpc_usd}  bounce={cp.bounce_rate_pct}%")
    print(f"  CR mobile={cp.mobile_conversion_rate_pct}% vs desktop={cp.desktop_conversion_rate_pct}% "
          f"(2.3× gap)")
    print(f"  funnel: page→form_start={cp.form_start_rate_pct}%, "
          f"start→submit={cp.form_completion_rate_pct}%")
    print(f"  ROAS={cp.roas}x  AOV=${cp.aov_usd}")
    print(f"  biggest_dropoff: {cp.biggest_dropoff_step_name!r}")

    t0 = time.monotonic()
    try:
        page_works, ctx, extras, hg, j, director, run_id = await run_full_pipeline_v3(
            BRIEF,
            retrieved_chunks=[],
            page_context=MOCK_PAGE,
            run_label="v3_realdata_homeiq",
            tags=["phase5d1", "realdata", "homeiq"],
        )
    except Exception as e:
        print(f"\n💥 PIPELINE FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    elapsed = time.monotonic() - t0
    print(f"\n✅ Pipeline succeeded in {elapsed:.1f}s — run_id={run_id}\n")

    # ── Page-Works summary ────────────────────────────────────────────────────
    if page_works:
        print("=" * 95)
        print("PAGE-WORKS — does it now use bounce/CR-split/funnel data?")
        print("=" * 95)
        print(f"\n  baseline_assessment: {page_works.baseline_assessment}  "
              f"confidence: {page_works.confidence:.2f}")
        print("\n  WARNINGS FOR DOWNSTREAM (look for funnel/CR-split references):")
        for w in page_works.warnings_for_downstream:
            print(f"    ⚠ {w}")
        print("\n  WORKING MECHANISMS SUMMARY:")
        print(f"    {page_works.working_mechanisms_summary}")

    # ── Director Decision ─────────────────────────────────────────────────────
    print("\n" + "=" * 95)
    print("🎯 PRODUCT DIRECTOR — does it now do ROI math?")
    print("=" * 95)
    print(f"\n  Confidence: {director.confidence:.2f}")
    print(f"  Ship: {len(director.shipped_plans)}  "
          f"Iterate: {len(director.iterate_plans)}  "
          f"Kill: {len(director.killed_plans)}")

    print(f"\n  📋 STRATEGIC RECOMMENDATION (look for $ / CPA / ROAS references):")
    print(f"    {director.strategic_recommendation}")

    if director.shipped_plans:
        print(f"\n  ✅ SHIP ({len(director.shipped_plans)}):")
        for sp in director.shipped_plans:
            parallel = f", parallel_group={sp.parallel_group}" if sp.parallel_group else ""
            print(f"    [{sp.ship_order}] {sp.test_id}{parallel}")
            print(f"        sample/arm={sp.final_sample_size_per_arm} duration={sp.final_duration_days}d")
            print(f"        why first: {sp.why_this_first}")

    if director.iterate_plans:
        print(f"\n  🔄 ITERATE ({len(director.iterate_plans)}):")
        for ip in director.iterate_plans:
            print(f"    {ip.test_id} (owner: {ip.suggested_owner})")
            print(f"        blocker: {ip.blocker}")

    if director.killed_plans:
        print(f"\n  ❌ KILL ({len(director.killed_plans)}):")
        for kp in director.killed_plans:
            print(f"    {kp.test_id} ({kp.kill_category})")
            print(f"        reason: {kp.kill_reason}")

    if director.constraint_warnings:
        print(f"\n  ⚠ CONSTRAINT WARNINGS:")
        for w in director.constraint_warnings:
            print(f"    • {w}")

    if director.next_batch_focus:
        print(f"\n  📍 NEXT BATCH FOCUS:")
        print(f"    {director.next_batch_focus}")

    print(f"\n  Inspect: python scripts/inspect_run.py {run_id} --full")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
