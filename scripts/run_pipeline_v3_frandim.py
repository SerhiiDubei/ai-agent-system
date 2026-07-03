#!/usr/bin/env python
"""E2E test on REAL PRODUCTION SITE: frandim.com.ua

Construction company in Western Ukraine selling apartments.
Ukrainian language, lead capture page, 13y in market, no testimonials visible.

This is a fresh stress-test — no operating data provided (mimics how real
clients arrive — they often don't share traffic/budget initially).
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
    MarketingBrief,
    OperatingConstraints,
)
from ai_agent_system.marketing.full_pipeline_v3 import run_full_pipeline_v3
from ai_agent_system.marketing.page_context import PageContext


BRIEF = MarketingBrief(
    niche="real_estate_construction",
    parent_category="real_estate",
    market="UA-IF",  # Ivano-Frankivsk region
    language="uk",
    traffic_source_primary="meta",      # assumption — they have FB/IG link
    page_goal="lead_form",
    primary_metric="lead_form_submission_rate",
    brief=(
        "Франківський Дім — забудовник у Західній Україні (Івано-Франківськ, "
        "Ужгород, Трускавець) продає квартири в нових ЖК. На ринку 13 років, "
        "здали 2106 квартир, 25 будинків. Сайт пропонує: 'Замовити дзвінок' "
        "(2 поля), 'Забронювати квартиру', 'Залишити заявку'. Цільова аудиторія "
        "— молоді сім'ї та професіонали 25-50 років які купують квартиру в "
        "новобудові. Ціни від 1050 у.о/м². Поточний фокус: ЖК 'Скандинавія'. "
        "На сайті є: показники років/будинків/квартир, project photo galleries, "
        "construction progress videos, blog. ВІДСУТНІ: client testimonials, "
        "reviews. Goal: lead form submission з номером телефону для відділу продажу."
    ),
    business_constraints=(
        "Ukrainian market — currency in Ukrainian Hryvnia + USD equivalent. "
        "Real estate ad regulations vary; some Meta restrictions on housing in EU/US "
        "may not apply but caution advised."
    ),
    client_id="frandim_ua",
    operating_constraints=OperatingConstraints(
        # Operator hasn't provided any of this — system runs in degraded mode
        risk_appetite="balanced",
        prior_tests_tried=[],
        additional_notes=(
            "First engagement — operator hasn't shared traffic/baseline data yet. "
            "System should produce general recommendations + flag missing data in "
            "constraint_warnings. No CTR/ROAS/funnel data available."
        ),
    ),
    # current_performance left None — this is realistic for first engagement
)


# Page context built from WebFetch analysis (not full snapshot — minimal version)
MOCK_PAGE = PageContext(
    snapshot_id=999_002,
    viewport_used="desktop",
    url="https://frandim.com.ua/",
    title="Франківський Дім | Надійний забудовник у Вашому місті",
    meta_description=(
        "Франківський Дім — будівництво багатоквартирних житлових будинків, "
        "квартири з ремонтом, комерційні приміщення в Івано-Франківську, "
        "Ужгороді, Трускавці. 13 років на ринку, 2106 зданих квартир."
    ),
    page_archetype="lead_capture",
    archetype_confidence=0.78,  # hybrid (real-estate ecom + lead capture)
    detected_element_roles=[
        "hero_headline",
        "primary_cta",            # "Замовити дзвінок"
        "lead_form",              # multiple lead forms
        "trust_signals_numeric",  # 13 років / 2106 квартир / 25 будинків
        "project_gallery",        # photos
        "construction_progress",  # videos
        "blog_section",
        "social_links",
    ],
    forms_summary=[
        "Call request form (any viewport): 2 fields (name, phone) — submit='Замовити дзвінок'",
        "Apartment booking form: 5 fields (project, apartment#, name, phone, email) — submit='Забронювати квартиру'",
        "General inquiry form: 2 fields (name, phone) — submit='Залишити заявку'",
    ],
    friction_signals=[
        "No client testimonials or reviews visible — major trust gap for big-ticket purchase",
        "Three different forms with overlapping purpose may confuse visitors",
        "Hero headline is project-specific ('ЖК Скандинавія') vs evergreen brand promise — may need rotation",
        "No visible 'about the founders' / leadership story — important for trust on multi-year construction commitment",
    ],
    tech_stack=["WordPress", "Supsystic Maps plugin", "Likely Contact Form 7"],
    visible_copy_excerpt=(
        "# Продаж квартир у ЖК 'Скандинавія' — триває!\n\n"
        "Франківський Дім — це 13 років надійності та якості будівництва.\n\n"
        "## Наші досягнення\n"
        "- 13 років на ринку\n"
        "- 25 збудованих будинків\n"
        "- 2106 зданих квартир\n"
        "- 230+ комерційних приміщень\n\n"
        "## Чому обирають нас\n"
        "- Енергоефективні технології будівництва\n"
        "- Дотримання строків здачі об'єктів\n"
        "- Якісні будівельні матеріали\n"
        "- Власна виробнича база\n"
        "- Юридична чистота угод\n"
        "- Кваліфіковані фахівці\n\n"
        "## Поточні проєкти\n"
        "- ЖК 'Скандинавія' (Івано-Франківськ) — від 1050 у.о/м²\n"
        "- ЖК у Ужгороді\n"
        "- ЖК у Трускавці\n\n"
        "Замовити дзвінок →"
    ),
)


async def main() -> int:
    print("=" * 95)
    print("PIPELINE V3 — REAL PRODUCTION SITE: frandim.com.ua (Ukrainian real estate)")
    print("=" * 95)
    print(f"\nclient_id: {BRIEF.client_id}")
    print(f"niche: {BRIEF.niche} (parent: {BRIEF.parent_category})")
    print(f"market: {BRIEF.market}  language: {BRIEF.language}")
    print(f"page_goal: {BRIEF.page_goal}  metric: {BRIEF.primary_metric}")
    print(f"\noperating_constraints: NO traffic/baseline/budget data — degraded mode")
    print(f"current_performance: NONE (first engagement)")
    print()

    t0 = time.monotonic()
    try:
        page_works, ctx, extras, hg, j, director, run_id = await run_full_pipeline_v3(
            BRIEF,
            retrieved_chunks=[],
            page_context=MOCK_PAGE,
            run_label="v3_frandim_realsite",
            tags=["phase5d1", "realsite", "frandim", "ukrainian", "real_estate"],
        )
    except Exception as e:
        print(f"\n💥 PIPELINE FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    elapsed = time.monotonic() - t0
    print(f"\n✅ Pipeline succeeded in {elapsed:.1f}s — run_id={run_id}\n")

    # ── Page-Works output ─────────────────────────────────────────────────────
    if page_works:
        print("=" * 95)
        print("📋 PAGE-WORKS — what's already working on frandim.com.ua")
        print("=" * 95)
        print(f"\n  baseline_assessment: {page_works.baseline_assessment}  "
              f"confidence: {page_works.confidence:.2f}")
        print("\n  TRUST ANATOMY:")
        for tm in page_works.trust_anatomy:
            print(f"    • {tm.element} (~{tm.estimated_load_pct}% load)")
            print(f"        {tm.why_working[:140]}")
        print(f"\n  PRESERVE ({len(page_works.preservation_zones)}):")
        for pz in page_works.preservation_zones:
            print(f"    • {pz.element}")
            print(f"        reason: {pz.reason[:140]}")
        print(f"\n  CHANGE-SAFE ({len(page_works.change_safe_zones)}):")
        for cs in page_works.change_safe_zones:
            print(f"    • {cs.element}")
        print(f"\n  WARNINGS for downstream agents:")
        for w in page_works.warnings_for_downstream:
            print(f"    ⚠ {w[:160]}")

    # ── Director Decision ─────────────────────────────────────────────────────
    print("\n" + "=" * 95)
    print("🎯 PRODUCT DIRECTOR — what to ship / iterate / kill")
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
            print(f"    [{sp.ship_order}] {sp.test_id}")
            if sp.final_sample_size_per_arm:
                print(f"        sample/arm={sp.final_sample_size_per_arm} "
                      f"duration={sp.final_duration_days}d")
            print(f"        why first: {sp.why_this_first}")

    if director.iterate_plans:
        print(f"\n  🔄 ITERATE ({len(director.iterate_plans)}):")
        for ip in director.iterate_plans:
            print(f"    {ip.test_id} (owner: {ip.suggested_owner})")
            print(f"        blocker: {ip.blocker[:200]}")
            for fix in ip.what_to_fix[:2]:
                print(f"        → fix: {fix[:160]}")

    if director.killed_plans:
        print(f"\n  ❌ KILL ({len(director.killed_plans)}):")
        for kp in director.killed_plans:
            print(f"    {kp.test_id} ({kp.kill_category})")
            print(f"        reason: {kp.kill_reason[:200]}")

    if director.constraint_warnings:
        print(f"\n  ⚠ CONSTRAINT WARNINGS:")
        for w in director.constraint_warnings:
            print(f"    • {w[:200]}")

    if director.next_batch_focus:
        print(f"\n  📍 NEXT BATCH FOCUS:")
        print(f"    {director.next_batch_focus}")

    # ── Plans details ─────────────────────────────────────────────────────────
    print("\n" + "=" * 95)
    print(f"📦 ALL HG PLANS GENERATED ({len(hg.plans)})")
    print("=" * 95)
    for p in sorted(hg.plans, key=lambda x: x.ice_total, reverse=True):
        depth = getattr(p, "test_depth_level", "unspecified")
        print(f"\n  {p.test_id}  [{depth}, ICE={p.ice_total}]")
        print(f"    name: {p.name}")
        print(f"    persona: {p.target_persona_name!r}, stage: {p.awareness_stage_targeted}")
        print(f"    elements: {getattr(p, 'elements_changed', '?')}")
        print(f"    hypothesis: {p.hypothesis_statement[:180]}")
        if p.variants:
            print(f"    variants ({len(p.variants)}):")
            for v in p.variants[:2]:
                print(f"      - [{v.label}] {v.description[:100]}")

    print(f"\n{'=' * 95}")
    print(f"  Inspect full trace: python scripts/inspect_run.py {run_id} --full")
    print(f"  State written to: agents/<expert>/state/{BRIEF.client_id}/")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
