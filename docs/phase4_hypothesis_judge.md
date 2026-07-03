# Phase 4 — Hypothesis Judge — Complete

**Status:** ✅ Complete
**Date:** 2026-04-28
**Hypothesis:** "Skeptical critic agent finds blind spots optimist generator misses."
**Result:** CONFIRMED — judge's cross-plan observations identified gaps generator did not flag (no big-rock test, all-low-risk batch).

---

## Files created

- `src/ai_agent_system/hypotheses/judge_schemas.py`
  - `HypothesisJudgeOutput`, `JudgeVerdict`, `JudgeVerdictType`
  - 6 per-dimension scores (1-10): hypothesis_quality, variant_concreteness, persona_anchor, friction_grounding, sample_size_realism, ice_defensibility
  - Verdict triad: ship | iterate | kill (forces decision, no middle-ground)
- `prompts/hypothesis_judge/v1.md` — character card (~1300 words, 6 sections)
- `src/ai_agent_system/hypotheses/judge.py` — agent runner using `run_with_fallback_direct`

## Files updated

- `configs/agents.yml` — added `hypothesis_judge` (gpt-4o-mini default, temp=0.1 for deterministic verdicts)
- `src/ai_agent_system/hypotheses/__init__.py` — export judge schemas
- `src/ai_agent_system/hypotheses/schemas.py` — added `_normalize_awareness_stage` field validator (auto-corrects model confusion: 'intent' → 'product_aware')
- `scripts/run_full_pipeline.py` — added Step 3 (judge) + verdicts rendering
- `scripts/build_viz.py` — HJ status flipped from `todo` to `complete`

---

## Pipeline result on homeiq.io brief (E2E)

| Stage | Latency | Cost (~) | Output |
|---|---|---|---|
| Drafter v2 (5 agents) | 33.5s | $0.005 | 3 personas + 5 CRO seeds + voice + audience |
| Hypothesis Generator (sonnet-4.6) | 148.4s | $0.30 | 3 plans + 3 deferred |
| Hypothesis Judge (gpt-4o-mini) | **13.4s** | $0.001 | **1 ship / 2 iterate / 0 kill** + per-dim scores |
| **TOTAL** | **195.3s** | **$0.31** | Production-ready test program |

### Judge program assessment

> "Mixed results — 1 ship, 2 iterate. Strong friction grounding in T1 and T3, but T2 lacks clarity in success criteria. Consider enhancing persona anchoring across all tests."

### Cross-plan observations (system-level critique judge surfaced)

- "All plans target different personas, but T2 and T3 could benefit from stronger persona anchoring."
- "No big-rock test (Impact ≥ 7) in the batch."
- "All plans have a low-risk level; consider introducing a higher-risk test for greater impact."

These are real gaps. Generator did not flag them. Judge did.

### Per-plan verdicts

- **T1 (mobile form 4→3 fields)** → SHIP, 8/10. All dimensions 8-10. "Variant design change is specific and actionable for developers."
- **T2 (hero headline shortening)** → ITERATE, 6/10. Weaknesses: hypothesis lacks success criterion (7/10 hypothesis_quality), persona too generic (6/10 anchor). 3 actionable improvements provided.
- **T3 (trust badge near form)** → ITERATE, 5/10. Weaknesses: ICE confidence not well-supported, sample size on the low side. 3 improvements.

---

## Architecture insight: Generator + Judge separation

Generator's character: optimistic, broad, synthesizes possibilities.
Judge's character: skeptical, narrow, finds what's broken.

Two roles in one agent = compromise. Two specialists = depth in both.

The Judge ran on **gpt-4o-mini** — 11× faster than Sonnet (used by Generator), $0.001 vs $0.30. Pattern matching against critique frameworks doesn't need creative model.

## Smart auto-correction worked again

In this run: `'Florida Martha'` → matched by prefix to `'Florida Martha, 68, fall-risk grandmother'`. Model truncated; assembler caught and resolved. Without this safety net, pipeline would have crashed on `primary_persona_exists` cross-field validation.

## Schema robustness improvement

Added `_normalize_awareness_stage` field validator to handle the predictable confusion between Schwartz Awareness Stages (`unaware/problem_aware/...`) and UserFlow stages (`awareness/consideration/intent/action`). Model returns `'intent'` → auto-mapped to `'product_aware'`. No more pipeline crashes from this class of error.

---

## What's next

**Phase 5: Re-evaluate system health** — re-run the system audit (like the earlier health-score doc) to compare before/after Phase 0-4. Then identify next weakest link.

**Phase 4-v2 candidate** (deferred): auto-regenerate plans the Judge marked 'iterate' — feed back the per-dimension weaknesses to Generator, get new variants. Currently user does this manually.

**Phase 6**: Push the SHIPPED plans to a real A/B test platform (VWO/Convert/Optimizely or basic split).

**Phase 7**: Pull results back, compute lift, post-test reads.
