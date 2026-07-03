# Phase 0 — Observability + Parameterization Infrastructure

**Status:** ✅ Complete
**Date:** 2026-04-28
**Scope:** Foundation that ALL Phase 1+ agents will use

---

## What was built

| File | Role |
|---|---|
| `src/ai_agent_system/observability/models.py` | Pydantic schemas: `LogEvent`, `LLMCallRecord`, `AgentInvocationRecord`, `EventType` enum |
| `src/ai_agent_system/observability/agent_logger.py` | `AgentLogger` (singleton) → `RunLogger` → `AgentInvocationLogger` (3-level hierarchy) |
| `src/ai_agent_system/observability/config_loader.py` | YAML → typed `AgentsConfig`, resolves tier → model per agent |
| `configs/agents.yml` | All agent parameters in one place, with quality tiers |
| `scripts/inspect_run.py` | CLI: read run logs as color-coded timeline |
| `scripts/smoke_test_observability.py` | E2E test of the pipes — no LLM calls needed |

---

## How to use it

### 1. Switch quality globally (one line)

Edit `configs/agents.yml`:
```yaml
quality_tier: economy   # or balanced, or premium
```

| Tier | What it does | Use when |
|---|---|---|
| `economy` | All agents on `gpt-4o-mini`, fallback to `gpt-4o` | Dev, iteration, cost-sensitive runs |
| `balanced` | Default `gpt-4o-mini`, `customer_insights` + `voice_message` upgraded to `claude-sonnet-4.6` | Normal commercial work |
| `premium` | All agents on `claude-sonnet-4.6`, fallback chain `gpt-4o → gpt-4o-mini` | Top-quality demos / hero clients |

`marketing_judge` always stays on `gpt-4o-mini` (overridden) because judging is cheap and routine.

### 2. Override per agent (when one agent needs special model)

In `configs/agents.yml`, under any agent block:
```yaml
agents:
  customer_insights:
    temperature: 0.4
    model_override: anthropic/claude-sonnet-4.6   # always use sonnet here
    fallbacks_override: [openai/gpt-4o]           # custom fallback chain
```

### 3. Read what an agent did

After any run that uses the logger:
```bash
python scripts/inspect_run.py --list           # all today's runs
python scripts/inspect_run.py --latest         # most recent run timeline
python scripts/inspect_run.py <run_id>         # specific run
python scripts/inspect_run.py <run_id> --full  # include full prompts + responses
```

### 4. Direct file access

Logs live at:
```
logs/agent_runs/<YYYY-MM-DD>/<run_id>.jsonl
```

Each line is one event. Greppable, jq-able:
```bash
jq -r '.event_type' logs/agent_runs/2026-04-28/<run_id>.jsonl | sort | uniq -c
jq 'select(.event_type=="llm_call_complete") | .payload.cost_usd' <run_id>.jsonl
```

---

## Key configuration decisions (signed off by you)

### Cost guardrails (commercial tier)
```yaml
per_run_max_usd: 0.50      # one end-to-end draft
per_agent_max_usd: 0.20    # one agent within a run
daily_total_max_usd: 25.00 # whole system per day
warn_at_pct: 0.75
```

### Retry policy
```yaml
retries: 1                          # one retry, then move to next fallback model
retry_on:
  - ValidationError
  - RateLimitError
  - APITimeoutError
retry_backoff_factor: 2.0
```

### Quality tier (default)
`economy` — cheapest. Switch to `balanced` for commercial deliverables.

---

## What this gives us going forward

Every Phase 1+ agent will:

1. **Be configured from YAML** — change model without touching code
2. **Log every LLM call** — system_prompt, user_prompt, raw_response, tokens, cost, latency
3. **Be inspectable** — one CLI command shows the whole timeline of any run
4. **Respect cost limits** — runaway loops can't drain budget
5. **Fall back gracefully** — if mini fails, gpt-4o picks up automatically

This is the foundation we needed before decomposing the drafter. Without it, debugging 5 parallel agents would be impossible.

---

## Open follow-ups

1. **Cost enforcement** — currently the limits are SET but not yet ENFORCED at runtime. Will be hooked into `LlmRouter.kill_switch` in Phase 1 when we wire the agents.
2. **Run UI** — CLI inspector is functional. A web view (FastAPI page reading JSONL) would be nice but is Phase 7+ territory.
3. **Centralized run-id propagation** — for now agents pass `run_id` explicitly. In Phase 1 we'll add a contextvar so agents auto-inherit from the request.

---

## Verified

```bash
$ python scripts/smoke_test_observability.py
$ python scripts/inspect_run.py --latest
```

Both green. Phase 0 complete.
