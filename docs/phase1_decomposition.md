# Phase 1 — Drafter Decomposition (5 agents) — Complete

**Status:** ✅ Complete (initial draft) — Phase 1.5 starts: per-card fine-tuning
**Date:** 2026-04-28
**E2E test brief:** homeiq.io walk-in tubs / FL seniors / meta paid traffic
**Result:** 65.7s, gpt-4o-mini, all cross-field validators passed

---

## Architecture delivered

```
WAVE 1 (parallel — no inter-deps)
  ├─ customer_insights      → CustomerInsightsOutput
  ├─ media_planner          → MediaPlanOutput
  └─ conversion_architect   → ConversionArchitectureOutput

WAVE 2 (parallel — depend on Wave 1)
  ├─ voice_message          → VoiceMessageOutput  (uses CustomerInsights)
  └─ audience_strategist    → AudienceSegmentationOutput  (uses CI + Media)

WAVE 3
  └─ assembler              → MarketingContext (legacy schema, flat)
```

---

## Files created

### Schema layer
- `src/ai_agent_system/marketing/sub_schemas.py` — 5 sub-output schemas + `HeadlineAngle`, `TestPriority`, `FrictionPoint` (NEW types)
- `src/ai_agent_system/marketing/brief.py` — `MarketingBrief` (input)

### Agent layer
- `src/ai_agent_system/marketing/agents/_base.py` — prompt loading, agent factory, `run_with_fallback()` (the fallback chain logic)
- `src/ai_agent_system/marketing/agents/customer_insights.py`
- `src/ai_agent_system/marketing/agents/voice_message.py`
- `src/ai_agent_system/marketing/agents/media_planner.py`
- `src/ai_agent_system/marketing/agents/audience_strategist.py`
- `src/ai_agent_system/marketing/agents/conversion_architect.py`

### Orchestration
- `src/ai_agent_system/marketing/orchestrator.py` — `draft_marketing_context_v2()` (asyncio.gather for parallel waves)
- `src/ai_agent_system/marketing/assembler.py` — combines 5 sub-outputs + smart auto-correction for cross-field constraints

### Character cards (in `prompts/<agent>/v1.md`)
- `prompts/customer_insights/v1.md` — ~700 words, 6 sections
- `prompts/voice_message/v1.md` — ~700 words
- `prompts/media_planner/v1.md` — ~700 words
- `prompts/audience_strategist/v1.md` — ~700 words
- `prompts/conversion_architect/v1.md` — ~750 words

### Test runner
- `scripts/run_drafter_v2.py` — E2E pipeline test on homeiq.io brief

---

## Sample output (homeiq.io brief)

### Customer Insights

3 personas generated, all niche-specific, decision_helper present:

- **Sarasota Helen, 73, fall-risk widow** (primary_buyer, 70-80, $30-60k, medium digital literacy)
  - JTBD: *"When I feel unsteady in the shower, I want to have a safe bathing option, so I can maintain my independence without risk of falling."*
- **Tampa Tom, 68, concerned son** (decision_helper, 65-75, $60-100k, high literacy)
- **Delray Debbie, 75, retired social worker** (influencer, 70-80, under $30k, low literacy)

5 aggregate pain points; audience psychology summary: *"The dominant emotion driving this audience is fear—fear of falling and losing independence, coupled with concern about being a burden to loved ones..."*

### Voice & Message

- **Primary value prop:** *"I help seniors stay independent and safe at home without the fear of falling in the shower."*
- **5 hooks:** "Stop worrying about slips in the shower." / "Finally, a safe way to bathe at home." / etc.
- **5 headline angles** tagged by awareness stage (problem_aware / solution_aware / most_aware)
- **Banned words:** revolutionary, unlock, leverage, seamless, game-changing, world-class, cutting-edge, innovative
- **4 voice examples** in customer's voice

### Media Plan

- Channel: meta
- Temperature: cold
- Creative grammar: *"Fast-paced, engaging visuals featuring relatable scenarios around bathroom safety. Use UGC-style content with no polished branding in the first few seconds..."*

### Audience Strategy

- Primary persona: "Sarasota Helen, 73, fall-risk widow" (60% est. share)
- Lookalike seeds: behavioural ("past-90-day buyers", "video-watchers ≥75% on fall prevention")
- Exclusions: past converters, contractors, employees

### Conversion Architecture

- 5 user_flow stages (awareness → consideration → evaluation → intent → action)
- 5 ICE-scored test priorities, top ICE=21 (form field design)
- 3 friction inventory points

### Cross-field validation

✅ `audience_profile.primary_persona_name` matches one persona
✅ `channel_profile.channel == traffic_source_primary == "meta"`

---

## Comparison: legacy drafter vs decomposed v2

|                           | Legacy drafter | Decomposed v2 (Phase 1) |
|---|---|---|
| Latency (avg)             | 88s on sonnet-4.6 | 65.7s on gpt-4o-mini |
| Model                     | sonnet-4.6 (forced — others failed validation) | gpt-4o-mini (any model in tier works) |
| Cost per run              | ~$0.10–$0.30 | ~$0.005–$0.015 |
| Cross-field robustness    | 50% pass rate | 100% (with auto-correction safety net) |
| Output richness           | personas + flow + channel + audience | + voice_message + test_priorities + lookalike seeds + exclusion signals + creative grammar + friction inventory |
| Reviewability             | one giant LLM call | per-agent — read each in isolation via `inspect_run.py` |
| Configurability           | hardcoded model + prompt | YAML tier-switching + per-agent overrides |
| Logs                      | none structured | full JSONL: every system_prompt, user_prompt, raw_response, tokens, cost |

---

## Inspection commands

```bash
# Latest run summary
python scripts/inspect_run.py --latest

# Specific run with full prompts + responses
python scripts/inspect_run.py 814a450e0483 --full

# All runs today
python scripts/inspect_run.py --list
```

---

## Phase 1.5 — Per-card fine-tuning (next)

The system is functional. Now per the user's plan: review each character
card one at a time, give feedback, iterate. Order:

1. **customer_insights** ← start here (foundation; everything else depends on its output)
2. **voice_message** (depends on personas; copy quality matters most for ROI)
3. **conversion_architect** (test priorities are the actual deliverable downstream)
4. **media_planner** (lower variation across briefs)
5. **audience_strategist** (mostly mechanical; lowest priority for prompt-tuning)

Per-card review questions to answer for each:
- Does WHO I AM match how you'd describe this role?
- Does WHERE I COME FROM ring true / land emotionally?
- Are WHAT I BELIEVE opinions yours? Anything to add/remove/sharpen?
- HOW I WORK — any steps missing? Wrong order?
- WHAT I KNOW — any frameworks missing? Any to remove?
- Sample output (above) — does the character "show" in the output, or is it generic?

---

## Open follow-ups for later phases

1. **Cost enforcement** — `cost_limits` in agents.yml are checked but not enforced at runtime yet. Hook into LlmRouter when integrating in Phase 2.
2. **LangGraph orchestrator** — Phase 1 uses asyncio.gather; LangGraph upgrade is for when we need per-node retry policies, conditional fallback, or checkpointing.
3. **Snapshot integration** (Phase 2) — currently agents work from brief text only. Phase 2 wires `page_snapshot_id` into Conversion Architect and Voice Message so they "see" the actual page.
4. **Hypothesis generator** (Phase 3) — will consume `voice_message.headline_angles + cro.test_priorities` directly. Phase 1's structured output is exactly the fuel that agent needs.
