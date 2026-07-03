#!/usr/bin/env python
"""Test Customer Insights v2 (agent-as-system) on 3 different niches.

Goal: prove that the SAME domain-agnostic agent produces good personas for:
  - walk-in tubs (senior care)
  - saas workflow tool (b2b saas)
  - debt relief (financial services)

If the agent is truly domain-agnostic, all three runs should produce
high-quality niche-appropriate personas without any niche-specific
hardcoding in the prompt.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_agent_system.marketing.agents_v2 import run_customer_insights_v2
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.observability.agent_logger import get_agent_logger
from ai_agent_system.observability.config_loader import load_agents_config


# ── 3 briefs from 3 totally different niches ──────────────────────────────────

BRIEFS = [
    MarketingBrief(
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
    ),

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
            "Target: Heads of Engineering at 50-500 person engineering orgs who are "
            "frustrated with Jira's complexity and want something AI-agent-friendly. "
            "Traffic: Google search (high intent: 'Linear alternative', 'Jira replacement'). "
            "Goal: book a demo. Sells team plans starting $15/seat/mo."
        ),
        business_constraints=None,
    ),

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
            "Target: 30-55 year olds with $15-50K credit card debt who are stretched and "
            "considering bankruptcy. Traffic: Meta ads. Goal: get them to fill a "
            "qualification form. Free consultation, no upfront fees, BBB A+ accredited, "
            "AFCC member, 12 years in business."
        ),
        business_constraints="Special Ad Category: credit — restricted targeting.",
    ),
]


async def main() -> int:
    print("=" * 95)
    print("CUSTOMER INSIGHTS V2 — domain-agnostic test on 3 different niches")
    print("=" * 95)

    cfg = load_agents_config()
    logger = get_agent_logger()

    results = []
    for i, brief in enumerate(BRIEFS, 1):
        print(f"\n{'='*95}")
        print(f"[{i}/{len(BRIEFS)}] Brief: niche={brief.niche!r} parent={brief.parent_category!r}")
        print(f"{'='*95}")

        run = logger.start_run(
            label=f"ci_v2_test_{brief.niche}",
            tags=["phase5b", "ci_v2", brief.niche],
        )
        t0 = time.monotonic()
        try:
            output = await run_customer_insights_v2(
                brief, retrieved_chunks=[], run_logger=run, cfg=cfg,
            )
            run.complete(payload={"personas": len(output.personas)})
            elapsed = time.monotonic() - t0
            print(f"\n✅ {elapsed:.1f}s  run_id={run.run_id}")
        except Exception as e:
            run.abort(reason=f"{type(e).__name__}: {e}")
            print(f"\n💥 FAILED: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            results.append({"brief": brief, "ok": False, "elapsed": time.monotonic() - t0,
                            "run_id": run.run_id})
            continue

        # ── Print persona summary ─────────────────────────────────────────────
        print(f"\n  PERSONAS ({len(output.personas)}):")
        for p in output.personas:
            print(f"    • {p.name}")
            print(f"        role={p.role}, age={p.age_range}, income={p.income_band}, "
                  f"literacy={p.digital_literacy}")
            print(f"        JTBD: {p.primary_job[:140]}")
            print(f"        pains: {len(p.pain_points)}, "
                  f"trust_needs: {len(p.trust_needs)}, "
                  f"objections: {len(p.objections)}")

        print(f"\n  AGGREGATE PAIN POINTS ({len(output.pain_points_aggregate)}):")
        for pp in output.pain_points_aggregate[:5]:
            print(f"    [{pp.severity}] {pp.label}: {pp.description[:90]}")

        print(f"\n  AUDIENCE PSYCHOLOGY SUMMARY:")
        print(f"    {output.audience_psychology_summary[:400]}")

        results.append({
            "brief": brief, "ok": True, "elapsed": time.monotonic() - t0,
            "run_id": run.run_id, "output": output,
        })

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n{'='*95}")
    print("SUMMARY")
    print(f"{'='*95}")
    print(f"{'Niche':<20}  {'Status':<12}  {'Time':<10}  {'Personas':<10}  {'Run ID'}")
    print("-" * 95)
    for r in results:
        status = "✅ pass" if r["ok"] else "❌ fail"
        n_personas = len(r["output"].personas) if r["ok"] else 0
        print(f"{r['brief'].niche:<20}  {status:<12}  {r['elapsed']:>5.1f}s    "
              f"{n_personas:<10}  {r['run_id']}")

    print(f"\n  Inspect any run with:  python scripts/inspect_run.py <run_id> --full")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
