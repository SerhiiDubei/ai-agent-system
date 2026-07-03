#!/usr/bin/env python
"""Multi-niche v3 pipeline test — proves domain-agnostic operation.

Runs the COMPLETE v3 pipeline (Page-Works → drafter → generator → judge → Director)
on 2 maximally different niches:
  1. SaaS workflow tool (B2B, demo-request, mid-traffic)
  2. Debt relief (financial services, lead-form, restricted Special Ad Cat)

Each niche has DIFFERENT operating constraints to prove Director adapts.
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


BRIEFS = [
    # SaaS — high traffic, low baseline, parallel-test feasible
    MarketingBrief(
        niche="saas_workflow",
        parent_category="b2b_saas",
        market="US",
        language="en",
        traffic_source_primary="google_search",
        page_goal="book_demo",
        primary_metric="demo_booking_rate",
        brief=(
            "FlowOps is a project tracking tool that competes with Linear and Jira. "
            "Target: Heads of Engineering at 50-500 person engineering orgs frustrated "
            "with Jira's complexity. Traffic: Google search (high intent: 'Linear alternative'). "
            "Goal: book a demo. $15/seat/mo team plans starting."
        ),
        client_id="flowops_saas",
        operating_constraints=OperatingConstraints(
            monthly_traffic_volume=80000,
            baseline_conversion_rate_pct=4.2,
            time_window_days=21,
            expected_lift_floor_pct=10.0,
            risk_appetite="experimental",
            prior_tests_tried=[
                "Hero CTA copy variants (Book demo / Get started / See it work) — Get started won by 8%",
            ],
        ),
    ),
    # Debt relief — low traffic, mid baseline, sequential-only
    MarketingBrief(
        niche="debt_relief",
        parent_category="financial_services",
        market="US",
        language="en",
        traffic_source_primary="meta",
        page_goal="lead_form",
        primary_metric="qualified_lead_rate",
        brief=(
            "DebtFreedom helps consumers settle $10K+ unsecured debt for less than they owe. "
            "Target: 30-55 year olds with $15-50K credit card debt. Traffic: Meta ads. "
            "Goal: qualification form fill. Free consultation, no upfront fees, BBB A+, "
            "AFCC member, 12 years in business."
        ),
        business_constraints="Special Ad Category: credit — restricted targeting.",
        client_id="debtfreedom_fs",
        operating_constraints=OperatingConstraints(
            monthly_traffic_volume=18000,
            baseline_conversion_rate_pct=14.7,
            time_window_days=14,
            expected_lift_floor_pct=6.0,
            risk_appetite="balanced",
            prior_tests_tried=[
                "Hero subhead variants — modest +3% lift in March",
                "Calculator widget input simplification — +9% in April",
            ],
        ),
    ),
]


async def main() -> int:
    print("=" * 95)
    print("FULL PIPELINE V3 — MULTI-NICHE TEST")
    print("=" * 95)

    results = []

    for i, brief in enumerate(BRIEFS, 1):
        print(f"\n{'=' * 95}")
        print(f"[{i}/{len(BRIEFS)}] niche={brief.niche!r} client_id={brief.client_id!r}")
        print(f"  traffic={brief.operating_constraints.monthly_traffic_volume}/mo "
              f"baseline={brief.operating_constraints.baseline_conversion_rate_pct}% "
              f"window={brief.operating_constraints.time_window_days}d "
              f"appetite={brief.operating_constraints.risk_appetite}")
        print(f"{'=' * 95}")

        t0 = time.monotonic()
        try:
            page_works, ctx, extras, hg, j, director, run_id = await run_full_pipeline_v3(
                brief,
                retrieved_chunks=[],
                page_context=None,  # no mock page for these niches — Page-Works runs structural-only
                run_label=f"v3_multi_{brief.niche}",
                tags=["phase5", "multi_niche", brief.niche],
            )
            elapsed = time.monotonic() - t0
            print(f"\n  ✅ {elapsed:.1f}s  run_id={run_id}")

            print(f"\n  📋 Strategic recommendation:")
            print(f"    {director.strategic_recommendation}")

            print(f"\n  Decisions: {len(director.shipped_plans)} ship / "
                  f"{len(director.iterate_plans)} iterate / {len(director.killed_plans)} kill")

            for sp in director.shipped_plans[:3]:
                print(f"    [SHIP {sp.ship_order}] {sp.test_id} (n/arm={sp.final_sample_size_per_arm})")

            for ip in director.iterate_plans[:2]:
                print(f"    [ITERATE] {ip.test_id}: {ip.blocker[:90]}")

            for kp in director.killed_plans[:2]:
                print(f"    [KILL] {kp.test_id}: {kp.kill_reason[:90]}")

            results.append({"niche": brief.niche, "ok": True, "elapsed": elapsed,
                            "run_id": run_id, "director": director, "page_works": page_works})

        except Exception as e:
            elapsed = time.monotonic() - t0
            print(f"\n  💥 {elapsed:.1f}s FAILED: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            results.append({"niche": brief.niche, "ok": False, "elapsed": elapsed})

    # Summary
    print(f"\n\n{'=' * 95}")
    print("SUMMARY")
    print(f"{'=' * 95}")
    print(f"{'Niche':<20} {'Status':<10} {'Time':<10} {'Ship/Iterate/Kill':<22} {'Run ID'}")
    print("-" * 95)
    for r in results:
        if r["ok"]:
            d = r["director"]
            verdicts = f"{len(d.shipped_plans)}/{len(d.iterate_plans)}/{len(d.killed_plans)}"
            print(f"{r['niche']:<20} {'✅ pass':<10} {r['elapsed']:>5.1f}s    "
                  f"{verdicts:<22} {r['run_id']}")
        else:
            print(f"{r['niche']:<20} {'💥 fail':<10} {r['elapsed']:>5.1f}s    -")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
