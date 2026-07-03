# Phase 5 — Agent-as-System Refactor (CI Prototype)

**Status:** 5b in progress (test pending)
**Date:** 2026-04-28
**Hypothesis:** "An agent built as a SYSTEM (identity + frameworks + market segments + golden sets, conditionally loaded) outperforms an agent built as a single hardcoded prompt — AND is domain-agnostic across niches."
**Result:** TBD after E2E test on 3 niches.

---

## The architectural shift

### Before (v1 — agent-as-prompt)

```
prompts/customer_insights/v1.md     ← single 2,300-word prompt
                                       with walk-in-tub examples
                                       baked into every section
```

**Problem:** the agent is implicitly "customer insights for senior care" because all examples in WHAT I BELIEVE / HOW I WORK / WHAT I KNOW / WHAT I PRODUCE reference walk-in tubs and senior personas. Run it on a B2B SaaS brief and quality drops because the agent has no "B2B SaaS knowledge" baked in.

### After (v2 — agent-as-system)

```
agents/customer_insights/
  AGENT.md                       ← domain-agnostic identity (no niche bake-in)
  beliefs.md                     ← 10 universal opinions
  workflow.md                    ← 6-step process with quality gates
  persona_filling_guide.md       ← output schema + how to fill
  anti_patterns.md               ← 18 cardinal sins to avoid

  knowledge/
    voc_mining.md                ← always-loaded
    frameworks/                  ← 10 framework files (Christensen, Moesta, Klement,
                                   Schwartz, CEPs, Maslow, Caregiver Burden, HBM,
                                   Kahan, Mom Test)
    market_segments/             ← 5 industry pattern files (senior_care, financial_
                                   services, b2b_saas, dtc_ecom, healthcare_consumer)

  golden_sets/                   ← 6 real persona examples as JSON few-shot:
    senior_care__paula_kohler_walkin
    senior_care__melanie_aplaceformom
    b2b_saas__chintan_linear
    healthcare__megan_talkspace
    financial_services__mary_national_debt
    dtc_ecom__careof_traveler

  segment_routing.yml            ← niche → segment + frameworks + goldens mapping
```

**At runtime:**
1. Loader reads brief's niche + brief text.
2. Selects segment (e.g. `walk_in_tubs` → `senior_care`).
3. Selects 5 default frameworks + 2-3 segment-specific (e.g. `caregiver_burden` for senior care, `moesta_forces_of_progress` for B2B).
4. Loads 1-2 golden_sets matching the segment.
5. Assembles all into a single rich system_prompt (~10-15K chars).
6. LLM call with that prompt + a brief user_prompt = persona output.

**Same agent, different brief = different knowledge loaded = niche-appropriate output, no hardcoding.**

---

## Files created

### Agent system files
| Path | Role | Words |
|---|---|---|
| `agents/customer_insights/AGENT.md` | Entry point + character | ~600 |
| `agents/customer_insights/beliefs.md` | 10 universal opinions | ~700 |
| `agents/customer_insights/workflow.md` | 6-step process + quality gates | ~1500 |
| `agents/customer_insights/persona_filling_guide.md` | Output schema + filling rules | ~1100 |
| `agents/customer_insights/anti_patterns.md` | 18 anti-patterns | ~900 |
| `agents/customer_insights/knowledge/voc_mining.md` | VoC source hierarchy | ~400 |
| `agents/customer_insights/knowledge/frameworks/*.md` | 10 frameworks | ~3000 total |
| `agents/customer_insights/knowledge/market_segments/*.md` | 5 segment patterns | ~3500 total |
| `agents/customer_insights/golden_sets/*.json` | 6 real persona examples | structured JSON |
| `agents/customer_insights/segment_routing.yml` | Niche → knowledge mapping | ~150 lines |

### Code files
- `src/ai_agent_system/marketing/agents_v2/system_loader.py` — loader + routing logic
- `src/ai_agent_system/marketing/agents_v2/customer_insights_v2.py` — agent runner

### Test
- `scripts/test_customer_insights_v2.py` — E2E test on 3 niches

---

## How routing works (segment_routing.yml)

3 fallback layers in order:

1. **Exact niche match** — if brief.niche is `walk_in_tubs`, look up the niches table → get segment + extra frameworks + golden_sets directly.

2. **Keyword match** — if no exact match, scan brief text for keywords. E.g. brief mentions "Medicare" → match senior_care segment. Brief mentions "SaaS" → b2b_saas segment.

3. **Catch-all** — no match → no segment loaded, just default frameworks + 2 diverse golden_sets for general guidance.

Default frameworks (always loaded):
- jtbd_christensen
- schwartz_awareness_stages
- sharp_romaniuk_ceps
- maslow_pain_mapping
- mom_test

---

## Why this is fundamentally different from v1

**v1**: ONE prompt that knew everything but could only really apply it to one niche (the niche the examples were drawn from).

**v2**: A SYSTEM that knows methodology generally, then reaches for the right reference material for the niche at hand. Same agent, different niche = different attached knowledge = niche-appropriate output.

This is exactly how Claude Code's **Skills** work: a skill is a folder with reference material + examples + instructions, loaded conditionally based on user request. We're applying that pattern to our marketing agents.

---

## Test plan (E2E)

Run CI v2 on 3 maximally different niches:
1. `walk_in_tubs` (senior care) — expects: decision_helper persona, fixed-income elder, caregiver_burden language
2. `saas_workflow` (B2B SaaS) — expects: champion + IT blocker personas, no income field, moesta_forces language
3. `debt_relief` (financial services) — expects: stretched-middle income, identity-protective language, "prior bad actor" objection

Success criteria:
- All 3 produce valid CustomerInsightsOutput (3-5 personas + aggregate pains + summary)
- Personas are NICHE-APPROPRIATE (not generic, not walk-in-tub-styled across all 3)
- Cross-niche language differs (senior care has "Mom slipped"; SaaS has "merged PRs/day"; fintech has "$1,020/mo minimums")
- Quality matches or exceeds v1 on the homeiq.io brief

---

## What stays in v1 for now

- All other agents (voice_message, media_planner, audience_strategist, conversion_architect, hypothesis_generator, hypothesis_judge) still use v1 pattern.
- Phase 5c will apply this same pattern to them ONLY AFTER CI prototype proves the architecture.

---

## Open follow-ups

1. **Selection mechanism for frameworks** — currently routing.yml is deterministic. A future variant could let an LLM decide which frameworks to load based on the brief — more flexible but harder to debug. Defer for now.

2. **Knowledge file freshness** — Frameworks and segment patterns drift over time (Meta changes, new privacy laws, new buying patterns). Need a quarterly review process for these files.

3. **Golden sets growth** — 6 examples is enough for proof-of-concept; production should grow to 20-40 spanning more niches.

4. **Loader caching** — system_loader reads files every call. For high-volume production, cache by (agent, routing_key) tuple.

5. **agent system viz** — viz/build_viz.py should show "v2 agent system" structure when an agent has been migrated, including which files were loaded for the latest run.
