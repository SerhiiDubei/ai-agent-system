#!/usr/bin/env python
"""End-to-end test: Full Pipeline v3 with Page-Works + Product Director + constraints.

Runs the COMPLETE Phase 5 pipeline on homeiq.io brief:
  Page-Works → CI v2 → (Voice, Media, Audience, CRO) → Generator → Judge → Director

Tests with operating_constraints (10k traffic, 21% baseline, 14-day window) to
prove the system adapts test recommendations to feasibility constraints.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_agent_system.marketing.brief import MarketingBrief, OperatingConstraints
from ai_agent_system.marketing.full_pipeline_v3 import run_full_pipeline_v3
from ai_agent_system.marketing.page_context import PageContext


# ── Brief with full operating constraints ─────────────────────────────────────

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
    client_id="homeiq_io",
    operating_constraints=OperatingConstraints(
        monthly_traffic_volume=12000,
        baseline_conversion_rate_pct=21.3,
        time_window_days=14,
        expected_lift_floor_pct=4.0,
        risk_appetite="balanced",
        prior_tests_tried=[
            "Reduced form fields 4→3, +6.2% in March 2026",
            "Hero subheadline tweak, no significant lift in April 2026",
        ],
        additional_notes=(
            "Operator's lead-quality is high — form is filtering effectively. "
            "Don't propose further form-field reduction without lead-quality evidence."
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
    print("FULL PIPELINE V3 — Page-Works + agents + Director (Phase 5)")
    print("=" * 95)
    print(f"\nclient_id: {BRIEF.client_id}")
    print(f"niche: {BRIEF.niche}")
    print(f"constraints: traffic={BRIEF.operating_constraints.monthly_traffic_volume}/mo "
          f"baseline={BRIEF.operating_constraints.baseline_conversion_rate_pct}% "
          f"window={BRIEF.operating_constraints.time_window_days}d "
          f"appetite={BRIEF.operating_constraints.risk_appetite}")
    print(f"prior_tests: {len(BRIEF.operating_constraints.prior_tests_tried)} entries")

    t0 = time.monotonic()
    try:
        page_works, ctx, extras, hg, j, director, run_id = await run_full_pipeline_v3(
            BRIEF,
            retrieved_chunks=[],
            page_context=MOCK_PAGE,
            run_label="v3_homeiq_full",
            tags=["phase5", "v3", "homeiq"],
        )
    except Exception as e:
        print(f"\n💥 PIPELINE FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    elapsed = time.monotonic() - t0
    print(f"\n✅ Pipeline succeeded in {elapsed:.1f}s")
    print(f"  run_id: {run_id}")

    # ── Page-Works summary ────────────────────────────────────────────────────
    if page_works:
        print("\n" + "=" * 95)
        print("PAGE-WORKS ANALYSIS")
        print("=" * 95)
        print(f"  baseline_assessment: {page_works.baseline_assessment}")
        print(f"  confidence: {page_works.confidence:.2f}")
        print(f"\n  Trust anatomy ({len(page_works.trust_anatomy)} mechanisms):")
        for tm in page_works.trust_anatomy:
            print(f"    • {tm.element} (~{tm.estimated_load_pct}% load)")
            print(f"        {tm.why_working[:120]}")
        print(f"\n  Preservation zones ({len(page_works.preservation_zones)}):")
        for pz in page_works.preservation_zones:
            print(f"    • {pz.element}: {pz.reason[:120]}")
        print(f"\n  Warnings for downstream ({len(page_works.warnings_for_downstream)}):")
        for w in page_works.warnings_for_downstream:
            print(f"    ⚠ {w[:140]}")

    # ── Hypothesis Generator + Judge ──────────────────────────────────────────
    print("\n" + "=" * 95)
    print(f"HYPOTHESIS PLANS ({len(hg.plans)})")
    print("=" * 95)
    for p in sorted(hg.plans, key=lambda x: x.ice_total, reverse=True):
        depth = getattr(p, "test_depth_level", "unspecified")
        print(f"\n  {p.test_id}: {p.name}")
        print(f"    depth={depth} ICE={p.ice_total} sample/arm={p.sample_size_per_arm_estimate}")
        print(f"    elements_changed={getattr(p, 'elements_changed', '(none)')}")

    # ── Product Director Decision (THE KEY OUTPUT) ────────────────────────────
    print("\n" + "=" * 95)
    print("🎯 PRODUCT DIRECTOR DECISION")
    print("=" * 95)
    print(f"\n  Confidence: {director.confidence:.2f}")
    print(f"  Ship: {len(director.shipped_plans)}  "
          f"Iterate: {len(director.iterate_plans)}  "
          f"Kill: {len(director.killed_plans)}")

    print(f"\n  📋 STRATEGIC RECOMMENDATION:")
    print(f"    {director.strategic_recommendation}")

    if director.shipped_plans:
        print(f"\n  ✅ SHIP ({len(director.shipped_plans)}):")
        for sp in director.shipped_plans:
            parallel = f", parallel_group={sp.parallel_group}" if sp.parallel_group else ""
            print(f"    [{sp.ship_order}] {sp.test_id}{parallel}")
            print(f"        sample/arm={sp.final_sample_size_per_arm} duration={sp.final_duration_days}d")
            print(f"        why first: {sp.why_this_first[:140]}")

    if director.iterate_plans:
        print(f"\n  🔄 ITERATE ({len(director.iterate_plans)}):")
        for ip in director.iterate_plans:
            print(f"    {ip.test_id} (owner: {ip.suggested_owner})")
            print(f"        blocker: {ip.blocker[:120]}")
            for fix in ip.what_to_fix[:3]:
                print(f"        → fix: {fix[:120]}")

    if director.killed_plans:
        print(f"\n  ❌ KILL ({len(director.killed_plans)}):")
        for kp in director.killed_plans:
            print(f"    {kp.test_id} (category: {kp.kill_category})")
            print(f"        reason: {kp.kill_reason[:140]}")

    if director.expert_conflicts_resolved:
        print(f"\n  ⚖ EXPERT CONFLICTS RESOLVED:")
        for c in director.expert_conflicts_resolved:
            print(f"    • {c[:140]}")

    if director.constraint_warnings:
        print(f"\n  ⚠ CONSTRAINT WARNINGS:")
        for w in director.constraint_warnings:
            print(f"    • {w[:140]}")

    if director.next_batch_focus:
        print(f"\n  📍 NEXT BATCH FOCUS:")
        print(f"    {director.next_batch_focus}")

    print(f"\n{'=' * 95}")
    print(f"  Inspect: python scripts/inspect_run.py {run_id} --full")
    print(f"  State saved at: agents/<expert>/state/{BRIEF.client_id}/")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
