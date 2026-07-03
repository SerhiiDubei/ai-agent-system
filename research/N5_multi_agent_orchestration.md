# Node N5 — Multi-Agent Orchestration Research

> **Scope:** LangGraph state machine orchestrating 2–4 expert agents (Copy Expert, UX/UI Expert, possibly more) on a shared landing-page snapshot input. Postgres checkpointing for durable resume. HITL via Obsidian markdown approval files. Cost tracking per node. Time-travel debugging.
> **Stack baseline (already decided):** Python 3.11 + FastAPI + LangGraph (now 1.0+) + Pydantic AI + pgvector + OpenRouter + Obsidian.
> **Date:** 2026-04-27.

---

## TL;DR

1. **Use a flat parallel fan-out / fan-in pattern (NOT a supervisor) for Round 1.** With only 2–4 expert agents reviewing the same immutable snapshot, a supervisor adds latency, an extra LLM call, and a non-trivial routing-eval surface for zero gain. The fan-out is deterministic (always all experts, always the same snapshot). Promote to a supervisor only if Sprint 7+ introduces dynamic agent selection or Cross-Review (Round 2).
2. **Pin `langgraph >= 1.0` and `langgraph-checkpoint-postgres >= 2.0.x`.** The September 2025 jump to 1.0 was deliberately a "no breaking changes" stabilization release. The risky upgrades historically lived in `langgraph-prebuilt` (1.0.2 broke deployments) and `langgraph-checkpoint-postgres` minor bumps after 2.0.21. Pin exact minor versions for both.
3. **Run a nightly checkpoint-pruner cron from day 1.** Every node write is a row. A 4-agent run with HITL pauses easily produces 30–60 checkpoint rows. At 100 runs/day that is ~5,000 rows/day, ~1.8M/year, and the `checkpoint_blobs` table (which holds the serialized state) grows several KB per row. Truncate by `thread_id` age + `status='completed'` flag.
4. **HITL via file-watcher polling, not direct interrupt resume.** Pydantic AI / LangGraph's `interrupt()` returns control to the *caller*. Bridge it with a separate FastAPI background task that polls the Obsidian vault for `status:` frontmatter changes, then calls `graph.ainvoke(Command(resume=…), config={"configurable": {"thread_id": …}})`. This keeps the agent process and the human loop fully decoupled.
5. **Cost tracking belongs in graph state with a typed reducer, mirrored to a separate `agent_run_costs` table on completion.** State-only loses history when threads are pruned; DB-only fights LangGraph's atomicity. Capture in state during the run, flush to DB on graph completion or HITL approval.
6. **Stream events for visibility, batch for the final hypothesis output.** Use `astream_events(version="v2")` to push per-node start/end and token-level deltas to the FastAPI SSE endpoint for the Obsidian dashboard. The hypothesis JSON itself is a structured Pydantic model — stream the *progress*, batch the *result*.
7. **Pydantic AI agents become LangGraph nodes by wrapping `agent.run()`** in an async function returning a partial state dict. Do not try to make Pydantic AI manage the graph — let LangGraph own orchestration, persistence, and HITL; let Pydantic AI own typed I/O, model routing (OpenRouter), and per-agent dependency injection.

---

## Top 5 existing solutions

| # | Project / Library | What it gives you | Verdict for N5 |
|---|---|---|---|
| 1 | **`langgraph` (core, 1.0+)** | StateGraph, Send API, interrupt/resume, checkpointers, streaming, retry policy. | **Must use.** Foundation. |
| 2 | **`langgraph-checkpoint-postgres` (2.0.x)** | `PostgresSaver` / `AsyncPostgresSaver` for durable resume across processes. | **Must use.** Pin exact minor. |
| 3 | **`langgraph-supervisor` (Python lib)** | High-level `create_supervisor([agents], model=…)` wrapper that adds a routing LLM in front of N agents. | **Skip for MVP.** Adds an LLM call you don't need. The LangChain team itself now recommends "supervisor-via-tools" hand-rolled instead of the lib. Reconsider for Round 2 (Cross-Review). |
| 4 | **`langgraph-swarm-py`** | Direct agent-to-agent handoff without a central router. | **Skip.** Swarm shines when agents pass the baton; our agents are independent reviewers, not collaborators in Round 1. |
| 5 | **`pydantic-ai` (>= 0.0.20+)** | Typed agents, model-agnostic provider routing, dependency injection, tool calling, `.iter()` for streaming. | **Must use.** Owns per-agent typed contract. |

**Honourable mentions (study, do not depend on):**
- `pydantic-ai-skills` (DougTrajano) — implements Anthropic's agentskills.io spec for Pydantic AI. Useful if you want filesystem-loaded role/rubric/examples files (see Q10 below).
- `langgraph-redis` (redis-developer) — alternative checkpointer if Postgres TTL pruning becomes painful. Has native TTL.
- Cole Medin's `coleam00/PydanticAI-Research-Agent` — the cleanest reference for how to organize a Pydantic AI codebase: `agents/`, `tools/`, `models/`, `config/`, with `.iter()` streaming to a Rich CLI. Closest stylistic match to what you're building.
- `vstorm-co/pydantic-deepagents` — Claude-Code-style deep agents on Pydantic AI; useful if you later need sub-agents.

---

## Code references worth studying

Specific files (with reason):

1. **`coleam00/PydanticAI-Research-Agent/agents/research_agent.py`** — clean single-agent Pydantic AI definition with system prompt, deps class, output model. Mirror this for your `CopyExpert`, `UXExpert` agents.
2. **`coleam00/PydanticAI-Research-Agent/agents/email_agent.py`** + **delegation in `research_agent.py`** — shows how one Pydantic AI agent calls another. You will *not* use this pattern (LangGraph orchestrates), but read it to understand what you're explicitly *not* doing.
3. **`coleam00/PydanticAI-Research-Agent/AGENTS.md`** — file conventions: 500-line cap, `agent.py / tools.py / models.py / dependencies.py` split. Adopt verbatim.
4. **`langchain-ai/langgraph-supervisor-py/langgraph_supervisor/supervisor.py`** — read `create_handoff_tool`. Even if you don't use the lib, the handoff tool pattern is the cleanest way to do Round 2 Cross-Review later.
5. **`langchain-ai/langgraph` examples → `examples/multi_agent/multi-agent-collaboration.ipynb`** — canonical fan-out + reducer + fan-in.
6. **`langchain-ai/langgraph` examples → `examples/human_in_the_loop/breakpoints.ipynb`** and **`dynamic_breakpoints.ipynb`** — the two interrupt patterns. You want dynamic, not static breakpoints.
7. **`extrawest/multi_agent_workflow_demo_in_langgraph`** — collection demonstrating supervisor, swarm, hierarchical, and parallel patterns side by side. Best place to A/B compare in code.
8. **`FareedKhan-dev/Multi-Agent-AI-System`** — multi-agent + LangSmith integration, useful if you later move from Logfire to LangSmith for tracing.

---

## Production case studies

- **AWS / DynamoDB durable agents (Nov 2025 blog)** — uses LangGraph with a custom `DynamoDBSaver` (lightweight metadata in DynamoDB, large payloads in S3) plus `enable_checkpoint_compression` and `ttl_seconds`. Confirms two production realities: (a) compression cuts checkpoint storage substantially, (b) TTL-based eviction is the only sane retention policy at scale. We borrow the mental model even though we're on Postgres.
- **Langfuse + LangGraph integration issues (GitHub langfuse#10962)** — when an `interrupt()` is involved, traces commonly fail to merge across the resume. Real-world cost: hours of debugging unfamiliar trace topology. Action: when you wire Logfire (or LangSmith), assert in a test that a single `thread_id` produces a single merged trace across interrupt+resume.
- **`langgraph-checkpoint-postgres` v2.0.21 → 2.0.22 silent breaking change (GitHub langgraph#5862)** — minor version bumps have shipped schema changes that break running deployments. Lesson: pin exact minor versions; gate the upgrade behind a migration script that runs `.setup()` in a maintenance window.
- **`langgraph-prebuilt==1.0.2` ungated breaking change (GitHub langgraph#6363)** — same lesson, different package. Pin `langgraph-prebuilt` even if you don't import from it directly (transitive).
- **"Unbounded growth" community post (langgraphjs#1138)** — the canonical "we ran out of disk because nobody pruned checkpoints" thread. Validates the nightly cron recommendation.

---

## Build vs buy verdict

**Buy:**
- LangGraph (orchestration, persistence, HITL primitives)
- Pydantic AI (typed agents, OpenRouter routing)
- `langgraph-checkpoint-postgres` (checkpointer)

**Build (thin wrappers on top):**
- The graph itself (50–100 lines; do not use `langgraph-supervisor` for MVP)
- File-watcher → resume bridge (FastAPI background task polling Obsidian vault, ~80 lines)
- Cost-tracking reducer + DB flush hook (~60 lines)
- Nightly checkpoint pruner (~30-line SQL job)
- Agent role/rubric loader (loads markdown files into Pydantic AI system prompts at startup, ~40 lines)

**Don't build:**
- A custom checkpointer (Postgres saver is fine)
- Your own retry/backoff (use `RetryPolicy`)
- Your own streaming protocol (use `astream_events(version="v2")`)
- A supervisor LLM in Round 1 (you don't need the routing intelligence)

---

## Concrete patterns to copy

### 1. Complete LangGraph state schema

```python
# src/orchestration/state.py
from __future__ import annotations
from datetime import datetime
from operator import add
from typing import Annotated, Literal, TypedDict
from typing_extensions import NotRequired

from pydantic import BaseModel, Field


class PageSnapshot(BaseModel):
    """Immutable input shared by all expert agents."""
    snapshot_id: str
    url: str
    headline: str
    subheadline: str | None
    cta_text: str
    body_text: str
    screenshot_path: str | None
    captured_at: datetime


class ExpertFinding(BaseModel):
    """One agent's structured output."""
    agent_name: Literal["copy", "ux", "offer", "trust"]
    severity: Literal["low", "medium", "high"]
    section: str                       # which section of page
    observation: str                   # what the expert sees
    hypothesis: str                    # proposed change
    expected_lift_pct: float | None    # optional quantitative bet
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = []            # rubric ids / heuristics referenced


class NodeCost(BaseModel):
    """One row of cost telemetry per node execution."""
    node_name: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    usd_cost: float
    duration_ms: int
    started_at: datetime


class AgentState(TypedDict):
    """LangGraph state. Reducers MUST be set on every list field
    that parallel nodes write to."""
    # ---- inputs (immutable) ----
    snapshot: PageSnapshot
    run_id: str

    # ---- per-agent outputs (parallel writes -> need reducer) ----
    findings: Annotated[list[ExpertFinding], add]

    # ---- cost telemetry (parallel writes -> need reducer) ----
    costs: Annotated[list[NodeCost], add]

    # ---- combined output (single writer: combiner node) ----
    combined_report: NotRequired[str]
    hypothesis_pack: NotRequired[dict]

    # ---- HITL ----
    approval_status: NotRequired[Literal["pending", "approved", "rejected", "edit"]]
    approval_note: NotRequired[str]

    # ---- error handling ----
    failed_agents: Annotated[list[str], add]   # agents that exhausted retries
```

Two non-obvious things:

- **Every parallel-written field needs a reducer.** Without `Annotated[list[...], add]` the second writer overwrites the first inside the same superstep. This is the #1 silent bug for fan-out graphs.
- **`NotRequired[...]` for fields added later.** Old in-flight checkpoints deserialize without crashing if the field is missing. Saves you a migration when you add `hypothesis_pack` in Sprint 7.

### 2. Parallel fan-out + fan-in pattern

```python
# src/orchestration/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .state import AgentState
from .nodes import (
    ingest_snapshot,
    copy_expert_node,
    ux_expert_node,
    offer_expert_node,
    trust_expert_node,
    combine_findings,
    request_human_approval,   # uses interrupt()
    persist_hypothesis_pack,
)

# Same retry policy for all expert agents.
EXPERT_RETRY = RetryPolicy(
    initial_interval=1.0,
    backoff_factor=2.0,
    max_interval=20.0,
    max_attempts=3,
    jitter=True,
    # default_retry_on already retries 5xx + transient httpx; we add timeouts.
    retry_on=(TimeoutError, ConnectionError),
)


def build_graph(checkpointer: AsyncPostgresSaver):
    g = StateGraph(AgentState)

    g.add_node("ingest", ingest_snapshot)

    # Fan-out: 4 expert nodes, each with its own retry policy.
    g.add_node("copy", copy_expert_node, retry_policy=EXPERT_RETRY)
    g.add_node("ux", ux_expert_node, retry_policy=EXPERT_RETRY)
    g.add_node("offer", offer_expert_node, retry_policy=EXPERT_RETRY)
    g.add_node("trust", trust_expert_node, retry_policy=EXPERT_RETRY)

    g.add_node("combine", combine_findings)
    g.add_node("approve", request_human_approval)        # interrupt()s here
    g.add_node("persist", persist_hypothesis_pack)

    # ingest fans out to all experts in parallel.
    g.add_edge(START, "ingest")
    for expert in ("copy", "ux", "offer", "trust"):
        g.add_edge("ingest", expert)
        g.add_edge(expert, "combine")    # fan-in via reducer on `findings`

    g.add_edge("combine", "approve")
    g.add_edge("approve", "persist")
    g.add_edge("persist", END)

    return g.compile(checkpointer=checkpointer)
```

The `for expert in (...)` loop creates 4 edges from `ingest` → expert, and 4 from expert → `combine`. LangGraph detects this as a single superstep, runs all 4 in parallel, and the `Annotated[list, add]` reducer on `findings` and `costs` merges the results.

### 3. HITL interrupt + resume pattern (file-based)

```python
# src/orchestration/nodes/approve.py
from langgraph.types import interrupt
from ..state import AgentState
from ..obsidian import write_approval_file


async def request_human_approval(state: AgentState) -> dict:
    """Writes a markdown file to the Obsidian vault, then interrupts.
    The graph pauses here until a separate process calls
    graph.ainvoke(Command(resume={...}), config={...thread_id...})."""
    md_path = await write_approval_file(
        run_id=state["run_id"],
        combined_report=state["combined_report"],
        findings=state["findings"],
    )

    # interrupt() persists state and raises GraphInterrupt; the caller
    # of graph.ainvoke catches it and returns control to FastAPI.
    decision = interrupt({
        "kind": "approval_required",
        "approval_file": str(md_path),
        "run_id": state["run_id"],
    })

    # Reached only AFTER resume.
    return {
        "approval_status": decision["status"],
        "approval_note": decision.get("note", ""),
    }
```

```python
# src/orchestration/resume_watcher.py — runs as FastAPI background task
import asyncio
from pathlib import Path

import frontmatter
from langgraph.types import Command


async def watch_obsidian_vault(graph, vault: Path, poll_seconds: float = 2.0):
    """Polls every approval markdown file. When `status:` frontmatter
    flips from 'pending' to approved/rejected/edit, resume the graph."""
    seen: dict[Path, str] = {}
    while True:
        for md in vault.glob("approvals/*.md"):
            post = frontmatter.load(md)
            status = post.get("status")
            if status == "pending":
                seen[md] = "pending"
                continue
            if seen.get(md) == status:
                continue                         # already resumed
            thread_id = post["thread_id"]
            note = post.get("note", "")
            await graph.ainvoke(
                Command(resume={"status": status, "note": note}),
                config={"configurable": {"thread_id": thread_id}},
            )
            seen[md] = status
        await asyncio.sleep(poll_seconds)
```

Key points:
- `interrupt(...)` raises a `GraphInterrupt` internally; `graph.ainvoke` returns with `__interrupt__` in the result.
- The thread is fully persisted in Postgres at this point; the FastAPI process can crash and the resume still works.
- Polling at 2s is fine. `watchdog`-based file events are more elegant but add a dep and don't survive Obsidian's atomic-rename-on-save dance reliably across OSes.
- The watcher de-dupes via `seen`; a more durable design uses `status_resumed_at:` frontmatter the watcher writes back.

### 4. Cost tracking decorator

```python
# src/orchestration/cost.py
import time
from datetime import datetime, timezone
from functools import wraps

from .state import NodeCost
from .pricing import price_for                  # OpenRouter price table


def track_cost(node_name: str):
    """Wraps a node so its returned dict gains a `costs: [NodeCost(...)]`
    entry. Relies on the node returning the Pydantic AI RunResult so we
    can read `.usage()`. Aggregated by the `Annotated[list, add]` reducer."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(state):
            t0 = time.perf_counter()
            result = await fn(state)
            usage = result.pop("__usage__", None)   # set by node body
            model = result.pop("__model__", "unknown")
            cost = NodeCost(
                node_name=node_name,
                model=model,
                input_tokens=usage.request_tokens if usage else 0,
                output_tokens=usage.response_tokens if usage else 0,
                cached_tokens=getattr(usage, "cached_tokens", 0) or 0,
                usd_cost=price_for(model, usage),
                duration_ms=int((time.perf_counter() - t0) * 1000),
                started_at=datetime.now(timezone.utc),
            )
            return {**result, "costs": [cost]}
        return wrapper
    return decorator
```

Usage in a node:
```python
@track_cost("copy_expert")
async def copy_expert_node(state: AgentState) -> dict:
    result = await copy_agent.run(
        user_prompt="Review this snapshot",
        deps=CopyDeps(snapshot=state["snapshot"]),
    )
    return {
        "findings": [result.output],         # reducer concatenates
        "__usage__": result.usage(),
        "__model__": "anthropic/claude-3.5-sonnet",
    }
```

Then mirror to a permanent table in `persist_hypothesis_pack`:
```python
async def persist_hypothesis_pack(state, *, db) -> dict:
    await db.executemany(
        "INSERT INTO agent_run_costs (run_id, node, model, in_tok, out_tok, "
        "cached_tok, usd, duration_ms, started_at) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [(state["run_id"], c.node_name, c.model, c.input_tokens,
          c.output_tokens, c.cached_tokens, c.usd_cost,
          c.duration_ms, c.started_at) for c in state["costs"]],
    )
    return {}
```
This survives checkpoint pruning and gives you a SQL-queryable cost table for "show me cost per agent per week."

### 5. Full mini-pipeline with 2 agents

```python
# examples/mini_two_agent_pipeline.py
import asyncio
from operator import add
from typing import Annotated, TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel
from pydantic_ai import Agent


# ---------- shared types ----------
class Snapshot(BaseModel):
    headline: str
    cta: str


class Finding(BaseModel):
    agent: str
    note: str


class State(TypedDict):
    snapshot: Snapshot
    findings: Annotated[list[Finding], add]


# ---------- two Pydantic AI agents ----------
copy_agent = Agent(
    "openrouter:anthropic/claude-3.5-sonnet",
    output_type=Finding,
    system_prompt="You are a direct-response copy expert. Critique the headline.",
)

ux_agent = Agent(
    "openrouter:openai/gpt-4o-mini",
    output_type=Finding,
    system_prompt="You are a UX expert. Critique the CTA.",
)


# ---------- graph nodes ----------
async def ingest(state: State) -> dict:
    return {}                                    # pass-through


async def copy_node(state: State) -> dict:
    r = await copy_agent.run(state["snapshot"].model_dump_json())
    return {"findings": [r.output.model_copy(update={"agent": "copy"})]}


async def ux_node(state: State) -> dict:
    r = await ux_agent.run(state["snapshot"].model_dump_json())
    return {"findings": [r.output.model_copy(update={"agent": "ux"})]}


async def combine(state: State) -> dict:
    print(f"Combined {len(state['findings'])} findings")
    for f in state["findings"]:
        print(f" - [{f.agent}] {f.note}")
    return {}


# ---------- graph ----------
async def main():
    async with AsyncPostgresSaver.from_conn_string(
        "postgresql://localhost/agentdb"
    ) as cp:
        await cp.setup()                         # idempotent

        g = StateGraph(State)
        g.add_node("ingest", ingest)
        g.add_node("copy", copy_node)
        g.add_node("ux", ux_node)
        g.add_node("combine", combine)
        g.add_edge(START, "ingest")
        g.add_edge("ingest", "copy")
        g.add_edge("ingest", "ux")
        g.add_edge("copy", "combine")
        g.add_edge("ux", "combine")
        g.add_edge("combine", END)
        graph = g.compile(checkpointer=cp)

        snap = Snapshot(headline="Buy our SaaS now", cta="Sign up")
        await graph.ainvoke(
            {"snapshot": snap, "findings": []},
            config={"configurable": {"thread_id": "demo-1"}},
        )

asyncio.run(main())
```

This is the smallest end-to-end thing that demonstrates: parallel fan-out, reducer-based fan-in, Pydantic AI typed I/O as graph nodes, durable checkpointing. ~70 lines. Build this as `examples/two_agent_smoke.py` first; only then scale to four real experts.

---

## Anti-patterns

1. **Forgetting reducers on parallel-written state fields.** `findings: list[Finding]` (no `Annotated`) means agent #4's output silently overwrites #1, #2, #3. The graph runs, no error, you ship a bug.
2. **Using a supervisor LLM for static fan-out.** A supervisor's job is *routing*. If the routing is "always run all 4 experts", you've added an LLM call (latency + cost + failure mode) to make a deterministic decision. Use plain edges.
3. **Calling `.invoke()` (sync) inside an async FastAPI handler.** Blocks the event loop, kills concurrency, gives you "30s response, 1 user at a time". Always `ainvoke` / `astream`.
4. **One Pydantic AI agent calling another via Pydantic AI's own delegation.** Works, but breaks LangGraph's view of the world: cost tracking, retries, time travel, and HITL won't see the inner call. Keep all inter-agent flow in LangGraph edges.
5. **Trying to make `interrupt()` block on a file change.** `interrupt()` is not a blocking primitive — it raises and unwinds. Anything that "waits for the file to change" must live *outside* the graph (the resume_watcher pattern above).
6. **Returning the full `RunResult` from a node.** Pydantic AI's `RunResult` includes message history that bloats checkpoints. Extract `.output` and `.usage()` only.
7. **Ignoring `.setup()` migrations on `langgraph-checkpoint-postgres` minor bumps.** A schema change in 2.0.22 will fail your prod queries silently. Run `.setup()` in a migration step in CI on every deploy.
8. **Single shared httpx client without a semaphore.** OpenRouter rate-limits. Four parallel agents on a hot run can burst past your tier. Use `asyncio.Semaphore(N)` keyed to the rate-limit ceiling, not the agent count.
9. **Trace fragmentation across `interrupt()`.** Logfire / LangSmith default trace IDs reset after a resume. Pass the parent trace context manually, or write a smoke test asserting one `thread_id` → one merged trace.
10. **`update_state` to "fix" a stuck thread.** It branches; it does not rewrite. The original checkpoint stays. Either accept the branch (good for time-travel) or delete the thread.
11. **Using `add_messages` for the `findings` list.** It's tempting because it's also a reducer for lists. But `add_messages` does dedup-by-id and is built for `BaseMessage`. Use plain `operator.add` for `list[ExpertFinding]`.
12. **Streaming the final hypothesis JSON.** Streaming partial JSON to a Pydantic-validated output type produces flickering invalid states. Stream events; batch the JSON.

---

## Recommended starter library set

```toml
# pyproject.toml — pin exact minor versions for the persistence stack
[project]
requires-python = ">=3.11,<3.13"
dependencies = [
  "langgraph>=1.0.0,<1.1",
  "langgraph-checkpoint>=2.0.0,<2.1",
  "langgraph-checkpoint-postgres>=2.0.21,<2.1",   # pin away from .22 schema break
  "langgraph-prebuilt>=1.0.0,<1.1",               # transitive but pin anyway
  "pydantic-ai>=0.0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.4",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "httpx>=0.27",
  "psycopg[binary,pool]>=3.2",                    # required by AsyncPostgresSaver
  "python-frontmatter>=1.1",                      # parse Obsidian markdown
  "tenacity>=9.0",                                # only if you need retry outside graph
  "logfire>=0.50",                                # Pydantic-native observability
]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "respx>=0.21",                                  # mock OpenRouter
  "pytest-postgresql>=6",                         # ephemeral pg for tests
]
```

Notes:
- `psycopg[binary,pool]>=3.2` is the version `AsyncPostgresSaver` actually wants. `psycopg2` will not work.
- `langgraph-supervisor` is intentionally *not* in the starter set. Add only if Round 2 ships.
- `langgraph-swarm-py` likewise — not for MVP.
- `logfire` over `langsmith` for MVP because it's a better fit for a Pydantic-AI-first codebase and free up to a generous tier.

---

## Open verifications

Things to validate empirically *in your own repo*, not from blogs:

1. **Trace merge across `interrupt()`** — write a test that runs the graph, interrupts, resumes 5 minutes later, and asserts Logfire shows one parent trace covering both legs. (Documented community failure mode.)
2. **Checkpoint blob size for a real 4-agent run.** Insert one synthetic run, query `SELECT pg_total_relation_size('checkpoint_blobs')`, multiply by your run-rate target. If > 1 GB / month, schedule the pruner cron for week 1, not "later".
3. **Pydantic AI `.usage()` field names on OpenRouter.** Different providers expose `request_tokens`, `prompt_tokens`, or `input_tokens`. Hit each model you actually plan to route to and assert your cost decorator reads them all correctly.
4. **`add` reducer on a Pydantic model list with the same `agent_name` from a retry.** Confirm a retried run does NOT produce two findings for the same agent in the combined list. Spec says only failing branches retry, so on success this is fine — but verify, because exponential duplication is a known bug class with `operator.add`.
5. **`.setup()` on existing tables.** Run twice against the same DB. Should be idempotent. Confirm before going to prod.
6. **Concurrency limit per OpenRouter key.** Pull your actual rate-limit ceiling, then size the `asyncio.Semaphore` accordingly. 4 agents × N parallel runs adds up fast.
7. **Resume after process crash.** Mid-run `kill -9` the FastAPI worker, restart, call `ainvoke(None, config={"thread_id":...})`. Should pick up at the last checkpoint. Verify *before* you depend on it.
8. **`langgraph-checkpoint-postgres` cleanup query.** Decide on retention (suggest: 30 days for completed, indefinite for `status='approved'`) and benchmark the DELETE query. The `checkpoint_writes` table can be the slow one.
9. **Round 1 latency with 4 parallel agents.** Run end-to-end 20 times, p50/p95. If p95 > 60s, you have UX work to do (streaming events to the dashboard becomes mandatory, not optional).
10. **Time-travel storage cost over 90 days of real traffic.** The blog estimates are not your estimates.

---

## Sources

- [LangGraph 1.0 release announcement and migration guide (Oct 2025)](https://docs.langchain.com/oss/python/migrate/langgraph-v1)
- [LangGraph 1.0 changes for AI engineers](https://medium.com/@romerorico.hugo/langgraph-1-0-released-no-breaking-changes-all-the-hard-won-lessons-8939d500ca7c)
- [LangGraph supervisor library (Python)](https://github.com/langchain-ai/langgraph-supervisor-py)
- [Multi-agent orchestration: supervisor vs swarm tradeoffs](https://focused.io/lab/multi-agent-orchestration-in-langgraph-supervisor-vs-swarm-tradeoffs-and-architecture)
- [Building multi-agent systems with langgraph-supervisor (DEV)](https://dev.to/sreeni5018/building-multi-agent-systems-with-langgraph-supervisor-138i)
- [LangGraph workflows-and-agents docs](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph swarm library](https://github.com/langchain-ai/langgraph-swarm-py)
- [LangGraph Send API map-reduce pattern (Medium)](https://medium.com/ai-engineering-bootcamp/map-reduce-with-the-send-api-in-langgraph-29b92078b47d)
- [Scaling LangGraph: parallelization, subgraphs, map-reduce trade-offs](https://aipractitioner.substack.com/p/scaling-langgraph-agents-parallelization)
- [LangGraph parallel nodes (fanouts) best practices forum thread](https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900)
- [LangGraph state management 2026 best practices](https://eastondev.com/blog/en/posts/ai/20260424-langgraph-agent-architecture/)
- [Mastering LangGraph state management 2025](https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025)
- [LangGraph use-graph-api docs](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
- [`langgraph-checkpoint-postgres` PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/)
- [LangGraph persistence docs](https://docs.langchain.com/oss/javascript/langgraph/persistence)
- [Mastering LangGraph checkpointing 2025 best practices](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- [Issue: unbounded checkpoint table growth (langgraphjs#1138)](https://github.com/langchain-ai/langgraphjs/issues/1138)
- [Issue: breaking change in langgraph-prebuilt 1.0.2 (#6363)](https://github.com/langchain-ai/langgraph/issues/6363)
- [Issue: breaking minor in langgraph-checkpoint-postgres after 2.0.21 (#5862)](https://github.com/langchain-ai/langgraph/issues/5862)
- [LangGraph 2026 production-grade guide](https://dev.to/richard_dillon_b9c238186e/langgraph-20-the-definitive-guide-to-building-production-grade-ai-agents-in-2026-4j2b)
- [Deploy LangGraph to production tutorial 2026](https://rapidclaw.dev/blog/deploy-langgraph-production-tutorial-2026)
- [Production multi-agent system: state checkpointing, error recovery, observability](https://markaicode.com/langgraph-production-agent/)
- [LangGraph human-in-the-loop docs](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Interrupts and commands in LangGraph (DEV)](https://dev.to/jamesbmour/interrupts-and-commands-in-langgraph-building-human-in-the-loop-workflows-4ngl)
- [LangGraph interrupt() pattern walkthrough (BSWEN, Apr 2026)](https://docs.bswen.com/blog/2026-04-16-langgraph-human-in-the-loop/)
- [Issue: trace fragmentation across interrupt+resume (langfuse#10962)](https://github.com/langfuse/langfuse/issues/10962)
- [Auto-resuming challenges in LangGraph (forum)](https://forum.langchain.com/t/auto-resuming-challenges-in-langgraph/1657)
- [LangGraph time-travel docs](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [Time-travel concept overview](https://langchain-ai.github.io/langgraph/concepts/time-travel/)
- [Debugging non-deterministic LLM agents with checkpoint-based replay](https://dev.to/sreeni5018/debugging-non-deterministic-llm-agents-implementing-checkpoint-based-state-replay-with-langgraph-5171)
- [Build durable AI agents with LangGraph + DynamoDB (AWS, 2025)](https://aws.amazon.com/blogs/database/build-durable-ai-agents-with-langgraph-and-amazon-dynamodb/)
- [LangSmith cost tracking docs](https://docs.langchain.com/langsmith/cost-tracking)
- [How to obtain token usage from LangGraph (forum)](https://forum.langchain.com/t/how-to-obtain-token-usage-from-langgraph/1727)
- [Understanding LangGraph usage_metadata (forum)](https://forum.langchain.com/t/understanding-langgraph-usage-metadata/174)
- [Langfuse token & cost tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking)
- [MLflow LangGraph tracing integration](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/)
- [LangGraph error handling: retries & fallback strategies](https://machinelearningplus.com/gen-ai/langgraph-error-handling-retries-fallback-strategies/)
- [A beginner's guide to handling errors in LangGraph with RetryPolicy](https://dev.to/aiengineering/a-beginners-guide-to-handling-errors-in-langgraph-with-retry-policies-h22)
- [Enhanced state management & retries (LangGraph changelog)](https://changelog.langchain.com/announcements/enhanced-state-management-retries-in-langgraph-python)
- [RetryPolicy reference](https://reference.langchain.com/python/langgraph/types/RetryPolicy)
- [Advanced error handling strategies in LangGraph applications](https://sparkco.ai/blog/advanced-error-handling-strategies-in-langgraph-applications)
- [Best way to control flow after retries exhausted (forum)](https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574)
- [LangGraph streaming docs](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangGraph streaming events deep dive (DEV)](https://dev.to/programmingcentral/stop-your-langgraph-agents-from-being-a-black-box-the-power-of-streaming-events-1hao)
- [LangGraph streaming 101: 5 modes](https://dev.to/sreeni5018/langgraph-streaming-101-5-modes-to-build-responsive-ai-applications-4p3f)
- [Async, parameters, and LangGraph (Medium)](https://medium.com/@danobenton/async-parameters-and-langgraph-oh-my-5a7b9d85f782)
- [Why I switched to async LangChain and LangGraph](https://nishant-mishra.medium.com/why-i-switched-to-async-langchain-and-langgraph-and-you-should-too-c30635c9cf19)
- [Python asyncio for LLM concurrency best practices](https://www.newline.co/@zaoyang/python-asyncio-for-llm-concurrency-best-practices--bc079176)
- [LangGraph best practices (Swarnendu De)](https://www.swarnendu.de/blog/langgraph-best-practices/)
- [Pydantic AI vs LangGraph (ZenML)](https://www.zenml.io/blog/pydantic-ai-vs-langgraph)
- [PydanticAI vs LangChain vs LangGraph 2026](https://aiagentskit.com/blog/pydantic-ai-vs-langchain-vs-langgraph/)
- [Building domain-specific AI agents with LangGraph + Pydantic AI](https://dotzlaw.com/ai-2/building-domain-specific-ai-agents-with-langgraph-and-pydantic-ai/)
- [Pydantic AI agents docs](https://ai.pydantic.dev/agent/)
- [Pydantic AI GitHub](https://github.com/pydantic/pydantic-ai)
- [pydantic-ai-skills (filesystem skill loading)](https://github.com/DougTrajano/pydantic-ai-skills)
- [coleam00/PydanticAI-Research-Agent reference repo](https://github.com/coleam00/PydanticAI-Research-Agent)
- [coleam00/PydanticAI-Research-Agent AGENTS.md conventions](https://github.com/coleam00/PydanticAI-Research-Agent/blob/main/AGENTS.md)
- [vstorm-co/pydantic-deepagents (Claude-Code-style deep agents on Pydantic AI)](https://github.com/vstorm-co/pydantic-deepagents)
- [Issue: unifying Pydantic AI + LangGraph traces in Logfire (opik#3432)](https://github.com/comet-ml/opik/issues/3432)
- [extrawest/multi_agent_workflow_demo_in_langgraph (pattern catalog)](https://github.com/extrawest/multi_agent_workflow_demo_in_langgraph)
- [FareedKhan-dev/Multi-Agent-AI-System (LangGraph + LangSmith)](https://github.com/FareedKhan-dev/Multi-Agent-AI-System)
- [LangGraph supervisor reference (Python)](https://reference.langchain.com/python/langgraph/supervisor/)
- [Multi-agent collaboration: latenode tutorial 2026](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-systems-complete-tutorial-examples)
- [LangGraph in 2026 (DEV community)](https://dev.to/ottoaria/langgraph-in-2026-build-multi-agent-ai-systems-that-actually-work-3h5)
