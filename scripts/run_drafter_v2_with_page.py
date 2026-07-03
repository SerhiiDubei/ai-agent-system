#!/usr/bin/env python
"""End-to-end test of decomposed drafter WITH page_context (Phase 2).

Uses a hand-crafted PageContext mimicking what a real homeiq.io snapshot
would produce — proves the integration works without requiring the
snapshot DB to be seeded.

Real production flow:
    1. snapshot/ module captures URL → DB row in page_snapshots
    2. semantic/ module classifies elements → DB row in semantic_maps
    3. brief.page_snapshot_id = <id>
    4. orchestrator auto-loads page_context from DB

This script SKIPS steps 1-3 by injecting a mock PageContext directly,
so we can validate the agent prompt integration today.
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
from ai_agent_system.marketing.page_context import PageContext

# ── Brief (same as Phase 1 test for direct comparison) ────────────────────────

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

# ── Hand-crafted page context (mimics what real snapshot would yield) ────────
# Approximates homeiq.io landing page from previous user-provided URL.

MOCK_PAGE = PageContext(
    snapshot_id=999_001,                 # synthetic — not in DB
    viewport_used="desktop",
    url="https://homeiq.io/walkintubs",
    title="Walk-In Tubs for Seniors | Free In-Home Assessment | HomeIQ",
    meta_description=(
        "Premium walk-in tubs designed for safety and comfort. "
        "Free in-home assessment from local installers. Veteran discounts available."
    ),
    page_archetype="lead_capture",
    archetype_confidence=0.92,
    detected_element_roles=[
        "hero_headline",
        "hero_subheadline",
        "primary_cta",
        "lead_form",
        "trust_badge",
        "testimonial",
    ],
    forms_summary=[
        "desktop form: 4 fields (zip, name, email, phone) — submit='Get My Free Assessment'",
        "mobile form: 4 fields (zip, name, email, phone) — submit='Get Started'",
    ],
    friction_signals=[
        "Mobile form has 4 fields — typical drop-off ~10-20% above 3 fields on mobile",
        "No visible phone number / click-to-call — common for senior audiences",
        "Hero headline length ~14 words — may exceed scan-time on mobile",
    ],
    tech_stack=["WordPress", "Elementor", "Google Tag Manager", "Meta Pixel", "Hotjar"],
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
        "## How It Works\n\n"
        "1. Enter your ZIP code\n"
        "2. We connect you with a local certified installer\n"
        "3. Schedule your free in-home assessment\n"
        "4. Get a custom quote with no obligation\n\n"
        '"After my fall last year, my daughter insisted I get a walk-in tub. '
        'HomeIQ made the whole process easy and the installer was wonderful." '
        "— Margaret, 74, Sarasota FL\n\n"
        "Get peace of mind today. Submit your ZIP to see if HomeIQ serves your area."
    ),
)


async def run_one(label: str, *, with_page: bool) -> tuple[float, str]:
    page = MOCK_PAGE if with_page else None
    t0 = time.monotonic()
    ctx, extras, run_id = await draft_marketing_context_v2(
        BRIEF,
        retrieved_chunks=[],
        page_context=page,
        run_label=label,
        tags=["phase2", "e2e", "mock_page" if with_page else "no_page"],
    )
    elapsed = time.monotonic() - t0
    return elapsed, run_id, ctx, extras


async def main() -> int:
    print("=" * 95)
    print("DRAFTER V2 — PHASE 2 — A/B TEST: with page_context vs without")
    print("=" * 95)

    print("\n[Run 1/2] WITHOUT page_context (Phase 1 baseline behavior)")
    elapsed_no, run_no, ctx_no, ex_no = await run_one(
        "phase2_baseline_no_page", with_page=False,
    )
    print(f"  ✓ {elapsed_no:.1f}s  run_id={run_no}")

    print("\n[Run 2/2] WITH mock page_context (Phase 2 enhanced behavior)")
    elapsed_yes, run_yes, ctx_yes, ex_yes = await run_one(
        "phase2_with_page", with_page=True,
    )
    print(f"  ✓ {elapsed_yes:.1f}s  run_id={run_yes}")

    # ── Diff: how does Conversion Architect's output change? ─────────────────
    print("\n" + "=" * 95)
    print("DIFF — Conversion Architect: friction_inventory")
    print("=" * 95)

    print("\n  WITHOUT PAGE (predicted friction):")
    for f in ex_no["cro_extras"]["friction_inventory"][:5]:
        print(f"    [{f['severity']}] {f['location']}: {f['issue']}")

    print("\n  WITH PAGE (grounded friction):")
    for f in ex_yes["cro_extras"]["friction_inventory"][:5]:
        print(f"    [{f['severity']}] {f['location']}: {f['issue']}")

    print("\n" + "=" * 95)
    print("DIFF — Conversion Architect: test_priorities (top 3 by ICE)")
    print("=" * 95)

    def top3(extras):
        tests = sorted(
            extras["cro_extras"]["test_priorities"],
            key=lambda t: t["impact_score"] + t["confidence_score"] + t["ease_score"],
            reverse=True,
        )
        return tests[:3]

    print("\n  WITHOUT PAGE:")
    for t in top3(ex_no):
        ice = t["impact_score"] + t["confidence_score"] + t["ease_score"]
        print(f"    [ICE={ice}] {t['element']}: {t['hypothesis'][:100]}")

    print("\n  WITH PAGE:")
    for t in top3(ex_yes):
        ice = t["impact_score"] + t["confidence_score"] + t["ease_score"]
        print(f"    [ICE={ice}] {t['element']}: {t['hypothesis'][:100]}")

    # ── Diff: Voice & Message — does it cite page copy now? ───────────────────
    print("\n" + "=" * 95)
    print("DIFF — Voice & Message: voice_examples")
    print("=" * 95)

    print("\n  WITHOUT PAGE (persona-only voice):")
    for q in ex_no["voice_message"]["voice_examples"][:3]:
        print(f"    \"{q[:120]}\"")

    print("\n  WITH PAGE (should include verbatim from page):")
    for q in ex_yes["voice_message"]["voice_examples"][:3]:
        print(f"    \"{q[:120]}\"")

    print("\n" + "=" * 95)
    print("DIFF — Voice & Message: hooks + headlines")
    print("=" * 95)
    print("\n  WITHOUT PAGE — sample headlines:")
    for h in ex_no["voice_message"]["headline_angles"]:
        print(f"    [{h['awareness_stage']}] {h['sample_headline']}")

    print("\n  WITH PAGE — sample headlines (should reference / outperform existing copy):")
    for h in ex_yes["voice_message"]["headline_angles"]:
        print(f"    [{h['awareness_stage']}] {h['sample_headline']}")

    # ── Inspect commands for full trace ──────────────────────────────────────
    print("\n" + "=" * 95)
    print(f"  Full inspection (system_prompts, raw_responses, cost):")
    print(f"    python scripts/inspect_run.py {run_no}  --full   # baseline")
    print(f"    python scripts/inspect_run.py {run_yes} --full   # with page")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
