#!/usr/bin/env python
"""End-to-end test of the decomposed drafter pipeline (Phase 1).

Runs the 5-agent pipeline on the homeiq.io walk-in tubs brief and
prints a human-readable summary. Full per-agent logs available via:

    python scripts/inspect_run.py <run_id>
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.orchestrator import draft_marketing_context_v2

# ── Test brief: homeiq.io / walk-in tubs / FL seniors / meta ──────────────────

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
        "Special Ad Category: housing — age/ZIP targeting blocked for US audiences. "
        "Creative must self-select audience without demographic filters."
    ),
)


async def main() -> int:
    print("=" * 90)
    print("DRAFTER V2 (DECOMPOSED) — E2E TEST on homeiq.io brief")
    print("=" * 90)

    t0 = time.monotonic()
    try:
        ctx, extras, run_id = await draft_marketing_context_v2(
            BRIEF,
            retrieved_chunks=[],          # no RAG for this test
            run_label="phase1_e2e_homeiq",
            tags=["phase1", "e2e", "homeiq"],
        )
    except Exception as e:
        print(f"\n💥 PIPELINE FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\nInspect agent runs with: python scripts/inspect_run.py --latest")
        return 1

    elapsed = time.monotonic() - t0

    # ── Print human-readable summary ─────────────────────────────────────────
    print(f"\n✅ Pipeline succeeded in {elapsed:.1f}s")
    print(f"   Run ID: {run_id}")
    print(f"   Inspect: python scripts/inspect_run.py {run_id}")
    print(f"   Full:    python scripts/inspect_run.py {run_id} --full")

    print("\n" + "=" * 90)
    print("CUSTOMER INSIGHTS — personas")
    print("=" * 90)
    for p in ctx.personas:
        print(f"\n  • {p.name}")
        print(f"    role={p.role}, age={p.age_range}, income={p.income_band}, "
              f"literacy={p.digital_literacy}")
        print(f"    JTBD: {p.primary_job}")
        print(f"    pains: {len(p.pain_points)}, "
              f"trust_needs: {len(p.trust_needs)}, "
              f"objections: {len(p.objections)}")

    print(f"\n  Aggregate pain points: {len(ctx.pain_points_aggregate)}")
    for pp in ctx.pain_points_aggregate[:3]:
        print(f"    - [{pp.severity}] {pp.label}: {pp.description[:80]}...")

    print(f"\n  Audience psychology summary:")
    print(f"    {extras['audience_psychology_summary'][:400]}...")

    print("\n" + "=" * 90)
    print("VOICE & MESSAGE STRATEGIST")
    print("=" * 90)
    vm = extras["voice_message"]
    print(f"\n  Primary value prop:")
    print(f"    \"{vm['primary_value_prop']}\"")
    print(f"\n  Hook variations ({len(vm['hook_variations'])}):")
    for h in vm["hook_variations"]:
        print(f"    • {h}")
    print(f"\n  Headline angles ({len(vm['headline_angles'])}):")
    for ha in vm["headline_angles"]:
        print(f"    • [{ha['awareness_stage']}] {ha['angle_name']}")
        print(f"      → {ha['sample_headline']!r}")
    print(f"\n  Banned words: {vm['banned_words'][:8]}")
    print(f"\n  Voice examples: {len(vm['voice_examples'])}")
    for q in vm["voice_examples"][:2]:
        print(f"    \"{q[:100]}...\"")

    print("\n" + "=" * 90)
    print("MEDIA PLANNER")
    print("=" * 90)
    print(f"  Channel: {ctx.channel_profile.channel}")
    print(f"  Channel temperature: {extras['media_extras']['channel_temperature']}")
    print(f"  Creative grammar:")
    print(f"    {extras['media_extras']['creative_grammar'][:400]}...")

    print("\n" + "=" * 90)
    print("AUDIENCE STRATEGIST")
    print("=" * 90)
    print(f"  Primary persona: {ctx.audience_profile.primary_persona_name!r}")
    print(f"  Estimated primary share: {ctx.audience_profile.estimated_primary_share:.0%}")
    print(f"\n  Lookalike seeds:")
    for s in extras["audience_extras"]["lookalike_seeds"]:
        print(f"    • {s}")
    print(f"\n  Exclusion signals:")
    for s in extras["audience_extras"]["exclusion_signals"]:
        print(f"    • {s}")

    print("\n" + "=" * 90)
    print("CONVERSION ARCHITECT")
    print("=" * 90)
    print(f"  User flow stages: {len(ctx.user_flow.stages)}")
    for s in ctx.user_flow.stages:
        print(f"    [{s.stage}] ({s.typical_duration}) — {s.description[:60]}")
    print(f"\n  Primary friction: {ctx.user_flow.primary_friction_point}")
    print(f"  Drop-off hypothesis: {ctx.user_flow.drop_off_hypothesis}")
    print(f"\n  Test priorities (sorted by ICE):")
    tests = sorted(
        extras["cro_extras"]["test_priorities"],
        key=lambda t: t["impact_score"] + t["confidence_score"] + t["ease_score"],
        reverse=True,
    )
    for t in tests:
        ice = t["impact_score"] + t["confidence_score"] + t["ease_score"]
        print(f"    [ICE={ice:2}] {t['element']}")
        print(f"             {t['hypothesis'][:90]}...")

    print(f"\n  Friction inventory: {len(extras['cro_extras']['friction_inventory'])} points")

    print("\n" + "=" * 90)
    print("FINAL CONTEXT VALIDATED ✅")
    print("=" * 90)
    print(f"\n  All cross-field validators passed:")
    print(f"    ✓ primary_persona_name '{ctx.audience_profile.primary_persona_name}' "
          f"exists in personas")
    print(f"    ✓ channel_profile.channel ({ctx.channel_profile.channel}) "
          f"== traffic_source_primary ({ctx.traffic_source_primary})")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
