#!/usr/bin/env python
"""End-to-end FULL pipeline test: brief → drafter v2 → hypothesis generator.

This is the complete value chain of the system as of Phase 3:
  1. Brief in (homeiq.io walk-in tubs)
  2. Decomposed drafter (5 agents) produces MarketingContext + extras
  3. Hypothesis Generator synthesizes 3-6 production-ready A/B test plans
  4. Output: ranked test program ready for human review / ship to VWO

After Phase 4 (Judge) we'll insert quality scoring between steps 3 and human review.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_agent_system.hypotheses.generator import generate_hypotheses
from ai_agent_system.hypotheses.judge import judge_hypotheses
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.orchestrator import draft_marketing_context_v2
from ai_agent_system.marketing.page_context import PageContext
from ai_agent_system.observability.agent_logger import get_agent_logger
from ai_agent_system.observability.config_loader import load_agents_config

# ── Brief and mock page (same as Phase 2) ─────────────────────────────────────

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
        "plus adult children helping aging parents make home-safety decisions. "
        "Traffic: Meta (Facebook / Instagram) paid ads. "
        "Goal: ZIP code submission so a local installer can follow up. "
        "Offer: Free in-home assessment, no high-pressure sales, veteran discounts."
    ),
    business_constraints=(
        "Special Ad Category: housing — age/ZIP targeting blocked for US audiences."
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
        "- 10-year warranty on installation\n"
        "- Veteran and military discounts\n"
        "- No high-pressure sales tactics\n\n"
        '"After my fall last year, my daughter insisted I get a walk-in tub. '
        'HomeIQ made the whole process easy and the installer was wonderful." '
        "— Margaret, 74, Sarasota FL"
    ),
)


async def main() -> int:
    print("=" * 95)
    print("FULL PIPELINE — brief → drafter v2 → hypothesis generator → judge")
    print("=" * 95)

    cfg = load_agents_config()
    logger = get_agent_logger()

    t0 = time.monotonic()

    # ── Step 1: Drafter v2 (5 agents → MarketingContext + extras) ────────────
    print("\n[1/3] Drafter v2 (5 agents) ...")
    drafter_t0 = time.monotonic()
    ctx, extras, drafter_run_id = await draft_marketing_context_v2(
        BRIEF,
        retrieved_chunks=[],
        page_context=MOCK_PAGE,
        run_label="full_pipeline_drafter",
        tags=["phase3", "full_pipeline"],
    )
    drafter_elapsed = time.monotonic() - drafter_t0
    print(f"  ✓ Drafter complete in {drafter_elapsed:.1f}s — "
          f"{len(ctx.personas)} personas, "
          f"{len(extras['cro_extras']['test_priorities'])} CRO seeds")
    print(f"  drafter_run_id = {drafter_run_id}")

    # ── Step 2: Hypothesis Generator ─────────────────────────────────────────
    print("\n[2/3] Hypothesis Generator (synthesizes test plans) ...")

    # Reuse the same RunLogger so timeline is continuous
    hg_run = logger.start_run(
        label="full_pipeline_hypotheses",
        tags=["phase3", "hypothesis_generator"],
    )
    hg_t0 = time.monotonic()
    try:
        hg_output = await generate_hypotheses(
            brief=BRIEF,
            ctx=ctx,
            extras=extras,
            page_context=MOCK_PAGE,
            run_logger=hg_run,
            cfg=cfg,
        )
        hg_run.complete(payload={"plans_count": len(hg_output.plans)})
    except Exception as e:
        hg_run.abort(reason=f"{type(e).__name__}: {e}")
        print(f"\n  💥 HYPOTHESIS GENERATOR FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    hg_elapsed = time.monotonic() - hg_t0
    print(f"  ✓ Hypothesis Generator complete in {hg_elapsed:.1f}s — "
          f"{len(hg_output.plans)} plans")
    print(f"  hypothesis_run_id = {hg_run.run_id}")

    # ── Step 3: Hypothesis Judge ─────────────────────────────────────────────
    print("\n[3/3] Hypothesis Judge (evaluates plans, ship/iterate/kill) ...")
    j_run = logger.start_run(
        label="full_pipeline_judge",
        tags=["phase4", "hypothesis_judge"],
    )
    j_t0 = time.monotonic()
    try:
        j_output = await judge_hypotheses(
            brief=BRIEF,
            ctx=ctx,
            extras=extras,
            hg_output=hg_output,
            page_context=MOCK_PAGE,
            run_logger=j_run,
            cfg=cfg,
        )
        j_run.complete(payload={
            "ship": j_output.ship_count,
            "iterate": j_output.iterate_count,
            "kill": j_output.kill_count,
        })
    except Exception as e:
        j_run.abort(reason=f"{type(e).__name__}: {e}")
        print(f"\n  💥 HYPOTHESIS JUDGE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    j_elapsed = time.monotonic() - j_t0
    print(f"  ✓ Hypothesis Judge complete in {j_elapsed:.1f}s — "
          f"{j_output.ship_count} ship / {j_output.iterate_count} iterate / "
          f"{j_output.kill_count} kill")
    print(f"  judge_run_id = {j_run.run_id}")

    total_elapsed = time.monotonic() - t0

    # ── Print readable summary ───────────────────────────────────────────────
    print("\n" + "=" * 95)
    print(f"TEST PROGRAM SUMMARY ({total_elapsed:.1f}s end-to-end)")
    print("=" * 95)
    print(f"\n{hg_output.test_program_summary}\n")

    print("=" * 95)
    print(f"A/B TEST PLANS ({len(hg_output.plans)}, ranked by ICE)")
    print("=" * 95)

    # Sort by ICE total descending for display
    plans_ranked = sorted(hg_output.plans, key=lambda p: p.ice_total, reverse=True)

    for i, p in enumerate(plans_ranked, 1):
        print(f"\n┌─ #{i} — {p.test_id}: {p.name}")
        print(f"│  ICE: {p.ice_total} (I={p.impact_score} C={p.confidence_score} E={p.ease_score})  "
              f"| risk={p.risk_level}  | effort={p.implementation_effort}")
        print(f"│  Targets: persona='{p.target_persona_name}', stage={p.awareness_stage_targeted}")
        if p.addressed_friction:
            print(f"│  Addresses friction: {p.addressed_friction[:120]}")
        print(f"│  Hypothesis:")
        print(f"│    {p.hypothesis_statement}")
        print(f"│  Variants ({len(p.variants)}):")
        for v in p.variants:
            print(f"│    [{v.label}] {v.description[:100]}")
            for c in v.copy_changes[:3]:
                print(f"│       copy: {c[:120]}")
            for d in v.design_changes[:3]:
                print(f"│       design: {d[:120]}")
        print(f"│  Success criteria:")
        for sc in p.success_criteria:
            primary_marker = " ⭐ PRIMARY" if sc.is_primary else ""
            print(f"│    - {sc.metric_name} should {sc.direction} "
                  f"by ≥{sc.minimum_detectable_lift_pct}%{primary_marker}")
        print(f"│  Expected lift: {p.expected_lift_range_pct}")
        if p.sample_size_per_arm_estimate:
            print(f"│  Sample size: {p.sample_size_per_arm_estimate:,}/arm "
                  f"(~{p.duration_estimate_days or '?'} days)")
        print(f"│  Rationale: {p.rationale[:200]}")
        print(f"└─")

    if hg_output.deferred_ideas:
        print(f"\n┌─ DEFERRED IDEAS ({len(hg_output.deferred_ideas)} backlog)")
        for d in hg_output.deferred_ideas:
            print(f"│  • {d}")
        print(f"└─")

    # ── Render Judge verdicts ────────────────────────────────────────────────
    print("\n" + "=" * 95)
    print("JUDGE PROGRAM ASSESSMENT")
    print("=" * 95)
    print(f"\n  {j_output.program_assessment}\n")
    print(f"  Ship: {j_output.ship_count}  |  Iterate: {j_output.iterate_count}  "
          f"|  Kill: {j_output.kill_count}")

    if j_output.cross_plan_observations:
        print(f"\n  Cross-plan observations:")
        for obs in j_output.cross_plan_observations:
            print(f"    • {obs}")

    print("\n" + "=" * 95)
    print(f"PER-PLAN VERDICTS")
    print("=" * 95)

    verdict_icon = {"ship": "✅ SHIP", "iterate": "🔄 ITERATE", "kill": "❌ KILL"}

    for v in j_output.verdicts:
        icon = verdict_icon.get(v.verdict, "?")
        print(f"\n┌─ {v.test_id}  →  {icon}  (overall {v.overall_score}/10)")
        print(f"│  Per-dimension scores:")
        print(f"│    hypothesis_quality   = {v.hypothesis_quality_score}/10")
        print(f"│    variant_concreteness = {v.variant_concreteness_score}/10")
        print(f"│    persona_anchor       = {v.persona_anchor_score}/10")
        print(f"│    friction_grounding   = {v.friction_grounding_score}/10")
        print(f"│    sample_size_realism  = {v.sample_size_realism_score}/10")
        print(f"│    ice_defensibility    = {v.ice_defensibility_score}/10")
        print(f"│  Strengths:")
        for s in v.strengths:
            print(f"│    + {s[:140]}")
        if v.weaknesses:
            print(f"│  Weaknesses:")
            for w in v.weaknesses:
                print(f"│    - {w[:140]}")
        if v.suggested_improvements:
            print(f"│  Suggested improvements:")
            for imp in v.suggested_improvements:
                print(f"│    → {imp[:140]}")
        print(f"└─")

    print(f"\n{'=' * 95}")
    print(f"  Full inspection (system_prompts, raw_responses, cost):")
    print(f"    python scripts/inspect_run.py {drafter_run_id}   --full  # drafter v2")
    print(f"    python scripts/inspect_run.py {hg_run.run_id}  --full  # hypothesis generator")
    print(f"    python scripts/inspect_run.py {j_run.run_id}   --full  # hypothesis judge")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
