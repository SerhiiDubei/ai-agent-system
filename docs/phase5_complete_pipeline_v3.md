# Phase 5 — Complete Pipeline v3 (Page-Works + agent-as-system + Director)

**Status:** All sub-phases complete (5d-new + 5f + 5g + 5h + part of 5i)
**Date:** 2026-04-28 (autonomous 3-hour build)
**Architecture pivot:** From "creative agency" mindset to "optimization consultancy" mindset

---

## What changed in Phase 5

### Mindset shift (the foundational change)

Before: agents proposed changes as if every page needed redesign. The system was implicitly modeling "AI creative agency that invents new things."

After: agents work from "what's already working" lens. The system explicitly models a "CRO consultancy that respects existing equity and proposes targeted, math-feasible tests."

### Architectural changes

#### 5d-new — Operating constraints as first-class input

`MarketingBrief` now has:
```python
operating_constraints: OperatingConstraints | None = Field(...)
```

with fields:
- `monthly_traffic_volume`
- `baseline_conversion_rate_pct`
- `time_window_days`
- `expected_lift_floor_pct`
- `risk_appetite` (conservative | balanced | experimental)
- `prior_tests_tried` (so we don't repeat)
- `additional_notes`

Plus:
- `client_id` for persistent state
- `TestDepthLevel` enum on `ABTestPlan` (basic | advanced | expert | super)
- `elements_changed` field on each plan
- `preservation_notes` field on each plan
- `mde_calculator.py` utility for sample-size + feasibility math

Files added:
- `src/ai_agent_system/hypotheses/mde_calculator.py`

Files modified:
- `src/ai_agent_system/marketing/brief.py`
- `src/ai_agent_system/hypotheses/schemas.py`

#### 5f — Page-Works Analyzer (NEW expert, FIRST in pipeline)

A NEW expert that runs BEFORE Customer Insights. Its job: identify what's already working on the existing LP so downstream experts can preserve it.

Output schema: `PageWorksAnalysis` with:
- `baseline_assessment` (works | partial | broken | unknown)
- `lift_scoring` (1-5 per LIFT lever, REVERSE — high = preserve)
- `trust_anatomy` (3-5 trust mechanisms with load-share %)
- `preservation_zones` (DO NOT TOUCH list)
- `change_safe_zones` (safer test surface)
- `warnings_for_downstream` (actionable, agent-targeted)
- `confidence` (0.0-1.0)

Knowledge files:
- `agents/page_works_analyzer/AGENT.md` — domain-agnostic identity
- `agents/page_works_analyzer/beliefs.md` — 9 universal opinions
- `agents/page_works_analyzer/workflow.md` — 5-step protocol
- `agents/page_works_analyzer/anti_patterns.md` — 17 cardinal sins
- `agents/page_works_analyzer/knowledge/frameworks/`:
  - `lift_model_reverse.md`
  - `trust_anatomy.md`
  - `page_archetype_patterns.md`
- `agents/page_works_analyzer/knowledge/working_page_patterns/`:
  - `senior_care.md`
  - `b2b_saas.md`
  - `financial_services.md`
  - `dtc_ecom.md`
  - `healthcare_consumer.md`
- `agents/page_works_analyzer/golden_sets/`:
  - `senior_care__working_walkin_tubs.json`
  - `b2b_saas__working_dev_tool.json`
  - `financial_services__working_debt_relief.json`

Code files:
- `src/ai_agent_system/page_works/__init__.py`
- `src/ai_agent_system/page_works/schemas.py`
- `src/ai_agent_system/page_works/analyzer.py`

#### 5g — Persistent Expert State (file-based v1)

Each agent has `agents/<agent>/state/<client_id>/` for accumulated knowledge across runs.

Files written per (agent, client) per run:
- `current_state.json` — latest output (overwritten)
- `versions/<ts>_v<n>.json` — append-only history
- `learnings.md` — append-only human-readable notes

Code files:
- `src/ai_agent_system/marketing/agents_v2/persistent_state.py`

API:
```python
state = load_current_state(agent_name, client_id)  # returns dict|None
save_current_state(agent_name, client_id, payload)
append_learning(agent_name, client_id, learning_text)
render_state_for_prompt(state)  # for prompt injection
```

For Phase 5 prototype: file-based. For production: migrate to Postgres.

#### 5h — Product Director (Senior CRO Program Director)

The synthesizer + final decision-maker. Reads ALL expert outputs + operating constraints + (eventually) persistent state, produces ranked ship/iterate/kill decisions.

Output schema: `ProductDirectorDecision` with:
- `shipped_plans` — sequenced (or parallel-grouped) ship recommendations
- `iterate_plans` — what to fix + which agent should fix it
- `killed_plans` — kill_reason + kill_category
- `strategic_recommendation` — PROGRAM-level (not test-level) advice
- `constraint_warnings` — operating constraint flags
- `expert_conflicts_resolved` — log of overruled experts
- `next_batch_focus` — what next quarter should explore
- `confidence` (0.0-1.0)

Knowledge files:
- `agents/product_director/AGENT.md`
- `agents/product_director/beliefs.md` — 10 universal opinions
- `agents/product_director/workflow.md` — 7-step protocol
- `agents/product_director/anti_patterns.md` — 18 cardinal sins
- `agents/product_director/knowledge/frameworks/test_program_management.md`
- `agents/product_director/knowledge/decision_patterns/common_archetypes.md`
- `agents/product_director/golden_sets/decision_low_traffic_high_baseline.json`

Code files:
- `src/ai_agent_system/product_director/__init__.py`
- `src/ai_agent_system/product_director/schemas.py`
- `src/ai_agent_system/product_director/director.py`

#### Specialization tags added to all v1 cards

Every agent now declares its specialization tags at the top of AGENT.md / character card. Foundation for future auto-routing + self-enrichment per `docs/agents_that_live_their_own_lives.md`.

Updated:
- `agents/customer_insights/AGENT.md`
- `prompts/voice_message/v1.md`
- `prompts/media_planner/v1.md`
- `prompts/audience_strategist/v1.md`
- `prompts/conversion_architect/v1.md`
- `prompts/hypothesis_generator/v1.md`
- `prompts/hypothesis_judge/v1.md`

#### Full pipeline v3 orchestrator

New: `src/ai_agent_system/marketing/full_pipeline_v3.py`

Topology:
```
WAVE 0: Page-Works Analyzer (NEW)
WAVE 1 (parallel): Customer Insights v2 + Media Planner + Conversion Architect
WAVE 2 (parallel): Voice Message + Audience Strategist
WAVE 3:            Assembler + Hypothesis Generator
WAVE 4:            Hypothesis Judge
WAVE 5:            Product Director (NEW)
```

Persistent state save after each major waved step (when `client_id` provided).

E2E test: `scripts/run_pipeline_v3.py`

---

## Schema layer additions

| Schema | File | Purpose |
|---|---|---|
| `OperatingConstraints` | `marketing/brief.py` | Real-world test feasibility constraints |
| `TestDepthLevel` enum | `hypotheses/schemas.py` | basic/advanced/expert/super |
| `ABTestPlan.test_depth_level` | `hypotheses/schemas.py` | New required field |
| `ABTestPlan.elements_changed` | `hypotheses/schemas.py` | Explicit list of changed elements |
| `ABTestPlan.preservation_notes` | `hypotheses/schemas.py` | What's preserved (page-works alignment) |
| `PageWorksAnalysis` | `page_works/schemas.py` | Page-Works output |
| `LiftScoring` | `page_works/schemas.py` | Per-LIFT-lever 1-5 reversal |
| `TrustMechanism` | `page_works/schemas.py` | One trust signal with load share |
| `PageElement` | `page_works/schemas.py` | Element with reason for preserve/safe |
| `ProductDirectorDecision` | `product_director/schemas.py` | Final decision package |
| `ShipDecision` / `IterateDecision` / `KillDecision` | `product_director/schemas.py` | Verdict types |
| `MarketingBrief.client_id` | `marketing/brief.py` | Persistent state key |

---

## Files created in Phase 5 (full inventory)

### Agent system files
- `agents/page_works_analyzer/AGENT.md`, `beliefs.md`, `workflow.md`, `anti_patterns.md`, `segment_routing.yml`
- `agents/page_works_analyzer/knowledge/frameworks/*.md` (3)
- `agents/page_works_analyzer/knowledge/working_page_patterns/*.md` (5)
- `agents/page_works_analyzer/golden_sets/*.json` (3)
- `agents/product_director/AGENT.md`, `beliefs.md`, `workflow.md`, `anti_patterns.md`, `segment_routing.yml`
- `agents/product_director/knowledge/frameworks/*.md`
- `agents/product_director/knowledge/decision_patterns/*.md`
- `agents/product_director/golden_sets/*.json`

### Code
- `src/ai_agent_system/hypotheses/mde_calculator.py`
- `src/ai_agent_system/page_works/__init__.py`, `schemas.py`, `analyzer.py`
- `src/ai_agent_system/product_director/__init__.py`, `schemas.py`, `director.py`
- `src/ai_agent_system/marketing/agents_v2/persistent_state.py`
- `src/ai_agent_system/marketing/full_pipeline_v3.py`

### Scripts
- `scripts/run_pipeline_v3.py`

### Docs
- `docs/research/04_persona_examples_and_frameworks.md`
- `docs/phase5_agent_as_system.md` (CI v2 prototype)
- `docs/phase5_complete_pipeline_v3.md` (this file)
- `docs/agents_that_live_their_own_lives.md` (vision doc)

### Updated
- `src/ai_agent_system/marketing/brief.py`
- `src/ai_agent_system/hypotheses/schemas.py`
- `src/ai_agent_system/marketing/agents_v2/system_loader.py` (auto-discovers core files)
- `configs/agents.yml` (added `page_works_analyzer`, `product_director`)

---

## What's still v1 (deferred to future session)

- Voice & Message Strategist — still v1 prompt (specialization tag added, but not full agent-as-system)
- Media Planner — same
- Audience Strategist — same
- Conversion Architect — same
- Hypothesis Generator — same
- Hypothesis Judge — same

These all have specialization tags now (foundation for future migration). Phase 5c will fully migrate them to agent-as-system structure.

---

## What's NOT done (deferred to future)

- 5e: Apply CI v2 learnings deeply to v1 cards (only specialization tags added so far)
- 5c: Full agent-as-system migration for the 6 v1 agents
- 5i: Preservation lens deeply integrated into existing experts (only happens via Page-Works warnings flowing through)
- 5j-5n: Auto-enrichment, knowledge provenance, daily background jobs (vision doc only)
- Phase 6: Test Platform integration (VWO/Convert)
- Phase 7: Results Tracker / Dashboard

---

## Open questions for user review

1. Confirm Page-Works Analyzer output schema and quality on first E2E run
2. Confirm Product Director decision quality (especially strategic_recommendation)
3. Confirm operating_constraints fields capture what real client briefs have
4. Confirm specialization tag set matches user's mental model (per agent)
5. Confirm vision doc `agents_that_live_their_own_lives.md` matches the long-term goal

---

## Quick-start: how to run the v3 pipeline

```python
from ai_agent_system.marketing.brief import MarketingBrief, OperatingConstraints
from ai_agent_system.marketing.full_pipeline_v3 import run_full_pipeline_v3
from ai_agent_system.marketing.page_context import PageContext

brief = MarketingBrief(
    niche="walk_in_tubs",
    parent_category="home_safety",
    market="US-FL",
    language="en",
    traffic_source_primary="meta",
    page_goal="zip_submit",
    primary_metric="zip_submit_rate",
    brief="HomeIQ sells walk-in tubs...",
    client_id="homeiq_io",
    operating_constraints=OperatingConstraints(
        monthly_traffic_volume=12000,
        baseline_conversion_rate_pct=21.3,
        time_window_days=14,
        expected_lift_floor_pct=4.0,
        risk_appetite="balanced",
        prior_tests_tried=["Form 4→3 fields, +6% in March 2026"],
    ),
)

page = PageContext(...)  # from snapshot or hand-crafted

(page_works, ctx, extras, hg, judge, director, run_id) = await run_full_pipeline_v3(
    brief, page_context=page, run_label="my_test_run",
)

print(f"Director's decision: {len(director.shipped_plans)} ship / "
      f"{len(director.iterate_plans)} iterate / {len(director.killed_plans)} kill")
print(f"Strategic: {director.strategic_recommendation}")
```

Or use the test script: `python scripts/run_pipeline_v3.py`

Inspect with: `python scripts/inspect_run.py <run_id> --full`
