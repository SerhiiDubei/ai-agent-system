# Multi-Agent Architecture Research

> Source: Research agent run on 2026-04-28
> Purpose: Inform decomposition of monolithic drafter into 5 specialized agents

## Framework Comparison

| Framework | Role definition | State passing | Parallelism | Failure handling |
|---|---|---|---|---|
| **LangGraph** | Each agent is a `node` (Python callable) on a `StateGraph`. Specialty in node's prompt + bound tools. | Shared `TypedDict` `AgentState`. Concurrent writes need `Reducer` (e.g. `Annotated[list, add]`). | Native: multiple outgoing edges fan out into same "superstep"; `Send` API for dynamic map-reduce. | `RetryPolicy(max_attempts, retry_on, jitter, backoff)` per node. Checkpointer persists successful nodes. Conditional edge to fallback. |
| **CrewAI (Crew)** | `Agent(role=, goal=, backstory=, tools=)`. Tasks declared separately. | Sequential: prev task's output appended as `context` to next. Hierarchical: `manager_llm` delegates. | Limited inside Crew. True parallel needs **Flows**. | Per-task `max_retries`. Weak vs LangGraph. |
| **CrewAI Flows** | Same Agent class, orchestration via `@start`/`@listen`/`@router` on Flow class with Pydantic state. | `self.state: BaseModel` thread-safe proxy. | Two `@listen(same_upstream)` auto-parallel. `and_/or_` for join logic. | try/except inside steps; `@router` for fallback. |
| **AutoGen** | `AssistantAgent(name=, system_message=)` + `GroupChatManager`. | Full chat history broadcast to every member. | Effectively none — turn-based. | None built in; cost explosion is documented failure mode. |
| **MetaGPT** | Hard-coded `Role` subclasses (PM, Architect, Engineer, QA) with `_actions` and `_watch`. | Global "message pool"; pub/sub via `_watch`. | Possible but opinionated toward sequential SDLC. | SOP-driven validation between stages. |
| **OpenAI Swarm/Agents SDK** | `Agent(instructions=, functions=)`. Handoff = function returning another Agent. | `context_variables` dict threaded through every call. | None native — one agent active at a time. | Minimal. |

## 5 Patterns to Copy

1. **LangGraph Reducers + Send API** — Define `MarketingContext` fields in `AgentState` with `Annotated[X, last_value]` for owned fields and `Annotated[list, add]` for accumulators. Fan agents out from entry node; LangGraph synchronizes join automatically.

2. **LangGraph `RetryPolicy` per node** — `retry=RetryPolicy(max_attempts=3, retry_on=(ValidationError, RateLimitError), backoff_factor=2)`. Critical because Pydantic ValidationError is exactly our failure mode. Note: wrap Pydantic AI call so `ValidationError` surfaces to runtime (LangGraph issue #6027).

3. **Pydantic AI "Programmatic Hand-Off"** — Don't make agents call each other as tools (bloats context). Orchestrator (LangGraph node body) calls `await persona_agent.run(brief, deps=shared_deps, usage=ctx.usage)` and writes typed result into state. Each agent only sees its own slice.

4. **MetaGPT's "SOP as prompt sequence"** — Specialty isn't just role string; it's an enforced output contract + intermediate validation. Each sub-agent has its own narrow Pydantic output model (`PersonaOutput`, `ChannelOutput`), not full 50-field schema. Validation failures stay local.

5. **CrewAI Flows `@listen` fan-in** — Mental model for "assembly" stage: a final method that runs once all predecessors complete, then assembles validated `MarketingContext`. LangGraph achieves via join node with list-reducer.

## Recommendation for Our Stack

**LangGraph as orchestrator + Pydantic AI for each sub-agent.** This is the dominant 2026 production combo. Matches our existing Pydantic AI bias.

**Topology:**
```
entry BriefSplitter (deterministic, derives per-agent context slices)
  → fan-out: 4 parallel edges to:
      PersonaCrafter, ChannelStrategist, FlowArchitect, AudienceAnalyst
  → join node
  → PainPointSynthesizer (sequential, depends on all 4)
  → Assembler (constructs final MarketingContext)
```

**State object:** `TypedDict` mirroring 5 sub-models + `errors: Annotated[list[AgentError], add]` + `brief: MarketingBrief`. Each agent owns disjoint write fields → no reducer conflicts.

**Failure handling:** per-node `RetryPolicy(max_attempts=3, retry_on=(ValidationError,))`. After exhaustion, node writes to `errors[]` and returns sentinel. Assembler reads `errors`; either (a) emit partial context flagged `degraded=True`, or (b) route via conditional edge to fallback node with cheaper model.

## Code Sketch

```python
from typing import Annotated, TypedDict
from operator import add
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy
from pydantic_ai import Agent
from pydantic import ValidationError

class CtxState(TypedDict):
    brief: MarketingBrief
    personas: list[Persona] | None
    channel_profile: ChannelProfile | None
    user_flow: UserFlow | None
    audience_profile: AudienceProfile | None
    pain_points: list[PainPoint] | None
    final: MarketingContext | None
    errors: Annotated[list[AgentError], add]

persona_agent = Agent("openai:gpt-4o", output_type=list[Persona], system_prompt=PERSONA_SP)
# ... 4 more agents

def make_node(agent, field):
    async def node(state: CtxState):
        try:
            r = await agent.run(state["brief"].model_dump_json())
            return {field: r.output}
        except ValidationError as e:
            return {field: None, "errors": [AgentError(field, str(e))]}
    return node

g = StateGraph(CtxState)
for name, agent, field in AGENTS:
    g.add_node(name, make_node(agent, field),
               retry=RetryPolicy(max_attempts=3, retry_on=(ValidationError,)))
    g.add_edge(START, name)
    g.add_edge(name, "pain")
g.add_node("pain", synthesize_pain, retry=RetryPolicy(max_attempts=3))
g.add_node("assemble", assemble)
g.add_edge("pain", "assemble"); g.add_edge("assemble", END)

graph = g.compile(checkpointer=SqliteSaver.from_conn_string("ctx.db"))
```

## Sources

- LangGraph Graph API overview (LangChain docs)
- LangGraph RetryPolicy reference
- LangGraph Multi-Agent Orchestration Guide 2025
- Pydantic AI Multi-Agent Patterns
- Combining LangGraph with Pydantic AI Agents
- CrewAI Processes (Sequential vs Hierarchical)
- CrewAI Flows
- AutoGen Group Chat design pattern
- MetaGPT GitHub (FoundationAgents) + paper (arXiv 2308.00352)
- OpenAI Swarm + Agents SDK Cookbook
