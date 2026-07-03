# Node N10 — LLM Gateway Research

**Stack context:** Python 3.11 + FastAPI + LangGraph + Pydantic AI + pgvector + OpenRouter + Obsidian. Output language: English.
**Scope:** Single-tenant gateway abstraction over OpenRouter providing per-operation routing, fallback chains, cost tracking, rate limiting, kill-switch, LangSmith tracing, and Pydantic AI integration.
**Date:** 2026-04-27.

---

## TL;DR

For a single-provider (OpenRouter) gateway with a moderate number of operations, **do not adopt LiteLLM**. Use the plain `openai` Python SDK (`AsyncOpenAI`) with `base_url="https://openrouter.ai/api/v1"` and build a thin in-process `LlmRouter` class (~300 LOC). LiteLLM brings a Postgres+Redis proxy server, virtual keys, and a 100+ provider abstraction you do not need; it also has known bugs around OpenRouter `cost` propagation in streaming mode. The native OpenRouter feature set (fallbacks via `extra_body.models`, provider pinning via `extra_body.provider.order`, `usage.cost` returned automatically in every response including the last SSE chunk in streaming) covers ~80% of what LiteLLM gives you for free.

For cost tracking, write one row per call to `llm_calls` (Postgres) with `operation_id`, `project_id`, `model_used`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `trace_id`, then materialize daily/monthly rollups (TimescaleDB continuous aggregates if you want it; otherwise plain `INSERT INTO llm_costs_daily ... ON CONFLICT DO UPDATE`). Rate limit with `aiolimiter.AsyncLimiter` (leaky bucket, asyncio-native, no Redis needed for single-process). Kill switch = single-row Postgres flag cached in-process with 5-second TTL. Retries with `tenacity` only for transient errors (`APIConnectionError`, `APITimeoutError`); leave rate-limit/server-error fallback to OpenRouter's native `extra_body.models` to avoid double-handling. LangSmith via `wrap_openai(AsyncOpenAI(...))` plus `LANGSMITH_TRACING=true` env — that's literally all the wiring needed. Pydantic AI agents use `pydantic_ai.models.openrouter.OpenRouterModel` which already wraps the same `AsyncOpenAI`; pass your custom client into its `Provider` so all calls flow through the same router and rate limiter.

---

## Top 5 existing solutions

### 1. LiteLLM (proxy + SDK)
- **What it is:** Open-source unified gateway for 100+ LLM providers. Two products: a Python SDK (`litellm.completion`) and a self-hosted proxy server with Postgres+Redis backing for keys, budgets, logs.
- **Strengths:** Drop-in OpenAI-compatible interface, built-in spend tracking by key/user/team, virtual keys, Prometheus metrics, model-cost map maintained centrally.
- **Weaknesses for our case:** Adds Postgres + Redis + a separate process to operate. Provides abstraction over many providers we don't use. Known bug: OpenRouter `usage.cost` is dropped in streaming responses through the proxy ([BerriAI/litellm #16021](https://github.com/BerriAI/litellm/issues/16021), [#11626](https://github.com/BerriAI/litellm/issues/11626)). Per-operation routing has to be encoded as virtual keys, which is awkward.
- **Verdict:** Overkill for one provider + ~10–20 operations.

### 2. OpenRouter native (with `openai` SDK)
- **What it is:** Use `openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1")`. Native fallback (`extra_body.models`), provider pinning (`extra_body.provider.order`), cost returned in `response.usage.cost` automatically.
- **Strengths:** Zero new infra. Already battle-tested by Pydantic AI's `OpenRouterModel`. `usage.cost` always present (last SSE chunk in stream mode) — no `stream_options.include_usage` needed anymore (deprecated).
- **Weaknesses:** No virtual keys for per-operation budget enforcement; you must build that yourself. Provider routing is limited to what OpenRouter exposes; pinning to e.g. "Anthropic direct, never Bedrock" is one line of config but you have to know the slugs.
- **Verdict:** This is the right primitive for us.

### 3. Portkey
- **What it is:** Hosted gateway with caching, fallbacks, observability. SDK + proxy.
- **Strengths:** Production-grade observability, semantic caching, guardrails.
- **Weaknesses:** Hosted SaaS ($) or self-hosted (yet another stack). OpenRouter already gives us routing — adding Portkey on top is double gateway.
- **Verdict:** Skip for v1.

### 4. Pydantic Logfire (with native OpenAI instrumentation)
- **What it is:** Pydantic's observability platform built on OpenTelemetry. Auto-instruments `openai`, `pydantic_ai`, `httpx`. ~8× cheaper than Arize, ~40× cheaper than LangSmith at moderate scale per Pydantic's own benchmarks.
- **Strengths:** Pydantic AI is first-party. OTel-native — you can also send to Jaeger/Tempo/Honeycomb. One-line setup.
- **Weaknesses:** Less prompt-engineering UI than LangSmith (no playground replay against a saved prompt).
- **Verdict:** Strong alternative to LangSmith. If LangSmith licensing or pricing becomes an issue, switch is one config change.

### 5. Langfuse (self-hosted)
- **What it is:** MIT-licensed self-hosted LLM observability platform. OTel-compatible. Strong on prompt versioning, evals, datasets.
- **Strengths:** Self-host on your Postgres; free forever. Best-in-class prompt management and dataset/eval workflow.
- **Weaknesses:** One more service to run; v1 setup requires ClickHouse for traces at scale.
- **Verdict:** Great option if you want full data ownership. Defer until eval infrastructure becomes important.

---

## Code references worth studying

- **Pydantic AI `OpenRouterModel`** (`pydantic_ai/models/openrouter.py`): canonical example of wrapping `OpenAIChatModel` for OpenRouter — settings type `OpenRouterModelSettings` exposes `openrouter_models` (fallbacks), `openrouter_provider` (routing), `openrouter_reasoning`, `openrouter_usage`, `openrouter_transforms`, `openrouter_preset`. Mirror this design for our `LlmRouter.call(operation_id, ...)` signature.
- **LiteLLM `cost_calculator.py`**: maintained pricing map (`model_prices_and_context_window.json`). Vendor this file as a fallback when OpenRouter doesn't return `usage.cost` (e.g. some BYOK paths return only `upstream_inference_cost`).
- **OpenRouter docs — Usage Accounting**: confirms that as of 2026 `usage.cost`, `usage.prompt_tokens`, `usage.completion_tokens`, `usage.prompt_tokens_details.cached_tokens`, `usage.completion_tokens_details.reasoning_tokens` are returned automatically, in the last SSE chunk for streams. The old `stream_options.include_usage=true` and `usage.include=true` are deprecated no-ops.
- **OpenRouter docs — Model Fallbacks / Provider Routing**: `extra_body={"models": [...]}` for model fallback chains; `extra_body={"provider": {"order": [...], "allow_fallbacks": False, "require_parameters": True, "data_collection": "deny"}}` for provider pinning. Use full slugs like `"google-vertex/us-east5"` for region pinning.
- **`langsmith.wrappers.wrap_openai`**: zero-config auto-instrumentation. Wraps an `openai.Client` or `openai.AsyncClient`; with `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`, every `chat.completions.create` becomes a span with messages, model, usage, latency. Combine with `@traceable` on the operation function for nested traces.
- **`aiolimiter.AsyncLimiter(max_rate, time_period)`**: leaky-bucket limiter usable as `async with limiter:`. Single dependency, no Redis.
- **`tenacity`**: `@retry(retry=retry_if_exception_type(APIConnectionError | APITimeoutError), wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(4))`. Do **not** retry `RateLimitError` here — let OpenRouter fallback handle it.

---

## Production case studies

- **LiteLLM at IBM (Nov 2025)**: documented Postgres schema for spend tracking — table `LiteLLM_SpendLogs(request_id, call_type, api_key, spend, total_tokens, prompt_tokens, completion_tokens, startTime, endTime, model, user, team_id, end_user, metadata)`. Worth copying the column set even if not the proxy.
- **OpenObserve / Portkey blog posts (2026)**: consensus pattern is "treat each LLM call as a first-class telemetry event, capture token counts, computed costs, model identifiers, and business context (operation, project) on every span". Aligns with LangSmith trace + Postgres row pattern below.
- **Pydantic Logfire pricing comparison (2026)**: at 50M spans/month, Logfire ~8× cheaper than Arize, ~27× cheaper than Langfuse Cloud, ~40× cheaper than LangSmith. For a single-tenant project the absolute cost difference is small, but if observability spend becomes meaningful, Logfire is the destination.
- **OpenRouter LiteLLM bug threads (#11626, #16021)**: real-world report that streaming `cost` is silently dropped through one layer of abstraction. Argument for staying close to the wire with the bare `openai` SDK.

---

## Build vs buy verdict

**Build a thin `LlmRouter` class in-process. Do not buy/adopt LiteLLM proxy.**

Rationale:
1. Single provider (OpenRouter) — multi-provider abstraction is wasted weight.
2. ~10–20 operations — virtual-key UX is not needed; YAML config of `llm.operations.<op_id>: <model>` is simpler.
3. OpenRouter native features (fallbacks, provider pinning, cost in `usage`) cover the gateway responsibilities.
4. Avoids running Postgres-for-LiteLLM + Redis-for-LiteLLM + a separate proxy process.
5. LangSmith / Logfire give us the observability layer; we don't need LiteLLM's logging.

**Buy** (managed/library, not custom): LangSmith for tracing (or Logfire), `aiolimiter`, `tenacity`, `openai`, `pydantic-ai`. Vendor LiteLLM's pricing JSON only as a cost fallback.

---

## Concrete patterns to copy

### A. `LlmRouter` — per-operation routing with shared async client

```python
# app/llm/router.py
from __future__ import annotations
import asyncio, time, uuid, yaml, httpx
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from aiolimiter import AsyncLimiter
from tenacity import retry, retry_if_exception_type, wait_random_exponential, stop_after_attempt

@dataclass(frozen=True)
class OpRoute:
    op_id: str
    primary: str
    fallbacks: tuple[str, ...] = ()
    provider_order: tuple[str, ...] = ()        # e.g. ("anthropic",) to pin direct
    allow_provider_fallback: bool = True
    require_parameters: bool = True
    max_tokens: int | None = None
    temperature: float | None = None
    soft_cost_cap_usd: float = 0.10             # per-call cap; warn if exceeded
    hard_cost_cap_usd: float = 1.00             # per-call cap; raise if exceeded

class LlmRouter:
    def __init__(
        self,
        api_key: str,
        config_path: str,
        kill_switch,                  # KillSwitch instance
        cost_sink,                    # CostSink instance
        max_concurrent: int = 64,
        rate_per_minute: int = 600,
    ):
        # One shared httpx client tuned for high concurrency. Not shareable
        # across event loops; create one per process.
        self._http = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=512, max_keepalive_connections=128),
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
        )
        raw = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            http_client=self._http,
            default_headers={
                "HTTP-Referer": "https://buggy.local",
                "X-Title": "buggy-agent-system",
            },
        )
        # wrap_openai is no-op when LANGSMITH_TRACING is unset.
        self.client: AsyncOpenAI = wrap_openai(raw)
        self.routes: dict[str, OpRoute] = self._load_routes(config_path)
        self.kill_switch = kill_switch
        self.cost_sink = cost_sink
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # Leaky bucket: rate_per_minute requests per 60s window.
        self.limiter = AsyncLimiter(rate_per_minute, 60)

    @staticmethod
    def _load_routes(path: str) -> dict[str, OpRoute]:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        out = {}
        for op_id, spec in cfg["llm"]["operations"].items():
            if isinstance(spec, str):
                out[op_id] = OpRoute(op_id=op_id, primary=spec)
            else:
                out[op_id] = OpRoute(
                    op_id=op_id,
                    primary=spec["model"],
                    fallbacks=tuple(spec.get("fallbacks", [])),
                    provider_order=tuple(spec.get("provider_order", [])),
                    allow_provider_fallback=spec.get("allow_provider_fallback", True),
                    require_parameters=spec.get("require_parameters", True),
                    max_tokens=spec.get("max_tokens"),
                    temperature=spec.get("temperature"),
                    soft_cost_cap_usd=spec.get("soft_cost_cap_usd", 0.10),
                    hard_cost_cap_usd=spec.get("hard_cost_cap_usd", 1.00),
                )
        return out

    def _build_extra_body(self, route: OpRoute) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if route.fallbacks:
            extra["models"] = list(route.fallbacks)        # OpenRouter native fallback
        if route.provider_order or not route.allow_provider_fallback:
            extra["provider"] = {
                "order": list(route.provider_order),
                "allow_fallbacks": route.allow_provider_fallback,
                "require_parameters": route.require_parameters,
                "data_collection": "deny",
            }
        return extra

    @traceable(run_type="llm")  # Wraps in a LangSmith span tagged with op_id.
    async def call(
        self,
        op_id: str,
        messages: list[dict],
        *,
        project_id: str,
        trace_id: str | None = None,
        **overrides,
    ) -> ChatCompletion:
        if not self.kill_switch.is_open():
            raise KillSwitchOpenError("LLM gateway is frozen")
        route = self.routes[op_id]
        trace_id = trace_id or str(uuid.uuid4())

        async with self.semaphore, self.limiter:
            return await self._call_inner(route, messages, project_id, trace_id, overrides)

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError)),
        wait=wait_random_exponential(min=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _call_inner(self, route, messages, project_id, trace_id, overrides):
        t0 = time.perf_counter()
        kwargs = {
            "model": route.primary,
            "messages": messages,
            "extra_body": self._build_extra_body(route),
            **{k: v for k, v in {
                "max_tokens": route.max_tokens,
                "temperature": route.temperature,
            }.items() if v is not None},
            **overrides,
        }
        resp: ChatCompletion = await self.client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        usage = resp.usage
        cost = float(getattr(usage, "cost", 0.0) or 0.0)
        if cost > route.hard_cost_cap_usd:
            await self.cost_sink.record(
                op_id=route.op_id, project_id=project_id, model_used=resp.model,
                prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
                cost_usd=cost, latency_ms=latency_ms, trace_id=trace_id, capped=True,
            )
            raise CostCapExceededError(f"{cost:.4f} > {route.hard_cost_cap_usd}")
        await self.cost_sink.record(
            op_id=route.op_id, project_id=project_id, model_used=resp.model,
            prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
            cost_usd=cost, latency_ms=latency_ms, trace_id=trace_id, capped=False,
        )
        return resp

    async def stream(
        self,
        op_id: str,
        messages: list[dict],
        *,
        project_id: str,
        trace_id: str | None = None,
        **overrides,
    ) -> AsyncIterator[ChatCompletionChunk]:
        if not self.kill_switch.is_open():
            raise KillSwitchOpenError("LLM gateway is frozen")
        route = self.routes[op_id]
        trace_id = trace_id or str(uuid.uuid4())

        async with self.semaphore, self.limiter:
            t0 = time.perf_counter()
            kwargs = {
                "model": route.primary,
                "messages": messages,
                "stream": True,
                "extra_body": self._build_extra_body(route),
                **overrides,
            }
            stream = await self.client.chat.completions.create(**kwargs)
            last_usage, model_used = None, route.primary
            async for chunk in stream:
                if chunk.usage is not None:        # Last SSE chunk only.
                    last_usage = chunk.usage
                if chunk.model:
                    model_used = chunk.model
                yield chunk
            latency_ms = int((time.perf_counter() - t0) * 1000)
            if last_usage is not None:
                cost = float(getattr(last_usage, "cost", 0.0) or 0.0)
                await self.cost_sink.record(
                    op_id=route.op_id, project_id=project_id, model_used=model_used,
                    prompt_tokens=last_usage.prompt_tokens,
                    completion_tokens=last_usage.completion_tokens,
                    cost_usd=cost, latency_ms=latency_ms, trace_id=trace_id, capped=False,
                )

    async def aclose(self) -> None:
        await self._http.aclose()


class KillSwitchOpenError(RuntimeError): ...
class CostCapExceededError(RuntimeError): ...
```

### B. YAML route config

```yaml
# config/llm.yaml
llm:
  operations:
    hypothesis_generation:
      model: anthropic/claude-sonnet-4.6
      fallbacks: [openai/gpt-4.1, google/gemini-2.5-pro]
      provider_order: [anthropic]                 # pin direct, no Bedrock
      allow_provider_fallback: false
      require_parameters: true
      max_tokens: 4096
      temperature: 0.7
      soft_cost_cap_usd: 0.20
      hard_cost_cap_usd: 1.50

    landing_summary:
      model: openai/gpt-4.1-mini
      fallbacks: [anthropic/claude-haiku-4.6]
      hard_cost_cap_usd: 0.10

    keyword_extraction: openai/gpt-4.1-nano       # short-form ok

    embeddings_default:
      model: openai/text-embedding-3-small
      hard_cost_cap_usd: 0.05
```

### C. Cost tracking — schema + sink

```sql
-- migrations/0001_llm_costs.sql
CREATE TABLE llm_calls (
    id            BIGSERIAL PRIMARY KEY,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    op_id         TEXT        NOT NULL,
    project_id    TEXT        NOT NULL,
    model_used    TEXT        NOT NULL,           -- actual model (post-fallback)
    prompt_tokens INTEGER     NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens  INTEGER     GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
    cost_usd      NUMERIC(12, 6) NOT NULL,
    latency_ms    INTEGER     NOT NULL,
    trace_id      TEXT        NOT NULL,
    capped        BOOLEAN     NOT NULL DEFAULT FALSE,
    extra         JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX llm_calls_proj_ts ON llm_calls (project_id, ts DESC);
CREATE INDEX llm_calls_op_ts   ON llm_calls (op_id, ts DESC);
CREATE INDEX llm_calls_trace   ON llm_calls (trace_id);

-- Daily rollup. If TimescaleDB is available, prefer a continuous aggregate.
CREATE TABLE llm_costs_daily (
    day        DATE NOT NULL,
    project_id TEXT NOT NULL,
    op_id      TEXT NOT NULL,
    model_used TEXT NOT NULL,
    calls      BIGINT NOT NULL,
    prompt_tokens BIGINT NOT NULL,
    completion_tokens BIGINT NOT NULL,
    cost_usd   NUMERIC(14, 6) NOT NULL,
    PRIMARY KEY (day, project_id, op_id, model_used)
);
```

```python
# app/llm/cost_sink.py
import asyncpg
from datetime import datetime, timezone

class CostSink:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def record(self, *, op_id, project_id, model_used,
                     prompt_tokens, completion_tokens, cost_usd,
                     latency_ms, trace_id, capped):
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("""
                INSERT INTO llm_calls
                  (op_id, project_id, model_used, prompt_tokens, completion_tokens,
                   cost_usd, latency_ms, trace_id, capped)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """, op_id, project_id, model_used, prompt_tokens, completion_tokens,
                 cost_usd, latency_ms, trace_id, capped)
            day = datetime.now(timezone.utc).date()
            await conn.execute("""
                INSERT INTO llm_costs_daily
                  (day, project_id, op_id, model_used, calls,
                   prompt_tokens, completion_tokens, cost_usd)
                VALUES ($1,$2,$3,$4,1,$5,$6,$7)
                ON CONFLICT (day, project_id, op_id, model_used) DO UPDATE SET
                  calls            = llm_costs_daily.calls + 1,
                  prompt_tokens    = llm_costs_daily.prompt_tokens + EXCLUDED.prompt_tokens,
                  completion_tokens= llm_costs_daily.completion_tokens + EXCLUDED.completion_tokens,
                  cost_usd         = llm_costs_daily.cost_usd + EXCLUDED.cost_usd
            """, day, project_id, op_id, model_used,
                 prompt_tokens, completion_tokens, cost_usd)
```

For monthly rollups, do `INSERT INTO llm_costs_monthly SELECT date_trunc('month', day) ...` from a cron job, or build a TimescaleDB hierarchical continuous aggregate over `llm_costs_daily`.

### D. Kill-switch state machine

```python
# app/llm/kill_switch.py
import time
import asyncpg

class KillSwitch:
    """
    Single boolean in Postgres, cached in-process. Open == calls allowed.
    Polling-with-TTL is enough for an admin manual switch (~5s latency).
    """
    def __init__(self, pool: asyncpg.Pool, ttl_seconds: float = 5.0):
        self.pool = pool
        self.ttl = ttl_seconds
        self._cached: bool = True
        self._fetched_at: float = 0.0

    async def ensure_table(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kill_switch (
                    name TEXT PRIMARY KEY,
                    open BOOLEAN NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    reason TEXT
                );
                INSERT INTO kill_switch (name, open) VALUES ('llm_gateway', TRUE)
                  ON CONFLICT (name) DO NOTHING;
            """)

    def is_open(self) -> bool:
        # Sync hot path; refresh lazily.
        now = time.monotonic()
        if now - self._fetched_at > self.ttl:
            # Schedule async refresh; return cached.
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._refresh())
            except RuntimeError:
                pass
        return self._cached

    async def _refresh(self):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT open FROM kill_switch WHERE name='llm_gateway'")
            self._cached = bool(row["open"]) if row else True
            self._fetched_at = time.monotonic()

    async def freeze(self, reason: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE kill_switch SET open=FALSE, reason=$1, updated_at=now() WHERE name='llm_gateway'",
                reason,
            )
        await self._refresh()

    async def thaw(self):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE kill_switch SET open=TRUE, reason=NULL, updated_at=now() WHERE name='llm_gateway'"
            )
        await self._refresh()
```

```python
# app/api/admin.py
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/admin/llm", tags=["admin"])

@router.post("/freeze")
async def freeze(reason: str, kill: KillSwitch = Depends(get_kill)):
    await kill.freeze(reason)
    return {"frozen": True, "reason": reason}

@router.post("/thaw")
async def thaw(kill: KillSwitch = Depends(get_kill)):
    await kill.thaw()
    return {"frozen": False}
```

In-flight calls finish naturally (no forced cancellation — that risks corrupted state in agents). New calls reject immediately at `LlmRouter.call`. If you need hard-cancel, expose a process-wide `asyncio.Event` and `await asyncio.wait([call_task, freeze_event.wait()], return_when=FIRST_COMPLETED)` in callers.

### E. Pydantic AI integration — share the same client

```python
# app/agents/factory.py
from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.providers.openrouter import OpenRouterProvider

def make_agent(router: LlmRouter, op_id: str, system_prompt: str) -> Agent:
    route = router.routes[op_id]
    # Reuse the wrapped AsyncOpenAI inside our LlmRouter so all calls flow through
    # the same LangSmith wrap, semaphore-bounded http client, and headers.
    provider = OpenRouterProvider(openai_client=router.client)
    model = OpenRouterModel(
        model_name=route.primary,
        provider=provider,
        settings=OpenRouterModelSettings(
            openrouter_models=list(route.fallbacks) or None,
            openrouter_provider={
                "order": list(route.provider_order),
                "allow_fallbacks": route.allow_provider_fallback,
                "require_parameters": route.require_parameters,
                "data_collection": "deny",
            } if route.provider_order else None,
            openrouter_usage={"include": True},
        ),
    )
    return Agent(model=model, system_prompt=system_prompt)
```

Caveat: when you call through Pydantic AI's `Agent.run`, cost recording does **not** flow through `LlmRouter.cost_sink` automatically. Either (a) hook Pydantic AI's `messages` / `usage` after `run` and call `cost_sink.record` yourself, or (b) instrument via Logfire / LangSmith and read costs from there. Option (a) is simpler:

```python
result = await agent.run(prompt)
u = result.usage()        # Pydantic AI's RunUsage
await router.cost_sink.record(
    op_id=op_id, project_id=project_id, model_used=route.primary,
    prompt_tokens=u.input_tokens, completion_tokens=u.output_tokens,
    cost_usd=u.cost or 0.0, latency_ms=int(u.duration_ms),
    trace_id=trace_id, capped=False,
)
```

### F. LangSmith trace correlation

```python
# Set once at startup (or in your FastAPI lifespan):
import os
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "buggy-prod"
# LANGSMITH_API_KEY should already be in env.

# Correlate LangSmith run_id with Postgres trace_id:
from langsmith import get_current_run_tree

@traceable
async def hypothesis_pipeline(project_id: str, brief: str, router: LlmRouter):
    run = get_current_run_tree()
    trace_id = str(run.id) if run else str(uuid.uuid4())
    return await router.call(
        "hypothesis_generation",
        [{"role": "user", "content": brief}],
        project_id=project_id,
        trace_id=trace_id,
    )
```

This way every Postgres `llm_calls.trace_id` matches the LangSmith run URL: `https://smith.langchain.com/o/<org>/projects/<proj>/r/<trace_id>`. To downsample tracing in production set `LANGSMITH_SAMPLING_RATE=0.1` (10% of root runs).

### G. Embeddings through the same gateway

```python
# app/llm/embeddings.py
class EmbeddingClient:
    def __init__(self, router: LlmRouter):
        self.router = router

    async def embed(self, op_id: str, inputs: list[str], *, project_id: str) -> list[list[float]]:
        route = self.router.routes[op_id]
        async with self.router.semaphore, self.router.limiter:
            t0 = time.perf_counter()
            resp = await self.router.client.embeddings.create(
                model=route.primary, input=inputs,
            )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            u = resp.usage
            cost = getattr(u, "cost", None) or _fallback_price(route.primary, u.total_tokens)
            await self.router.cost_sink.record(
                op_id=op_id, project_id=project_id, model_used=route.primary,
                prompt_tokens=u.prompt_tokens, completion_tokens=0,
                cost_usd=cost, latency_ms=latency_ms,
                trace_id=str(uuid.uuid4()), capped=False,
            )
        return [d.embedding for d in resp.data]
```

Embeddings go through OpenRouter's `/embeddings` endpoint (OpenAI-compatible). `usage.cost` may be missing on some embedding routes; vendor LiteLLM's `model_prices_and_context_window.json` and use it as `_fallback_price()`.

---

## Anti-patterns

- **Double-handling rate limits.** If you write app-level retries on `RateLimitError` *and* declare `extra_body.models` fallbacks, your retries fire first and the fallback never triggers. Pick one. Recommended: skip app retry on 429, let OpenRouter fall back to next model.
- **Sharing one `httpx.AsyncClient` across event loops** (e.g. across worker processes that re-init their own loops). HTTPX pools are per-loop. Build the client inside FastAPI's `lifespan` so it lives on the right loop.
- **Calling `wrap_openai` twice** on the same client. Creates duplicate spans for every call. Wrap once at construction; pass the wrapped client around.
- **Blocking on the kill switch.** Don't `await` Postgres on every `is_open()` — that adds latency to every LLM call. Cache + TTL is fine for a manual operator switch.
- **Putting `tenacity` retries *outside* the semaphore.** A retry loop that re-acquires the semaphore each attempt amplifies head-of-line blocking. Wrap retry inside the semaphore.
- **Trusting `usage.cost` blindly for BYOK.** For BYOK requests, only `cost_details.upstream_inference_cost` is populated. Fall back to vendored pricing if `cost == 0`.
- **Streaming without yielding the final usage chunk.** A common bug is `if not chunk.choices: continue` — this skips the last SSE chunk that carries usage. Always check `chunk.usage` before any `continue`.
- **Per-call `AsyncOpenAI()` instantiation.** Each `AsyncOpenAI` builds its own httpx pool. Construct once, share.
- **Killing in-flight calls on freeze.** Cancelling mid-stream leaves agent state inconsistent and you still get billed. Reject new calls only.
- **Per-operation Postgres connections.** Use `asyncpg.Pool` (min 5, max 20). Cost-sink writes should never be the bottleneck.
- **Logging full prompts to Postgres.** Use `extra` JSONB sparingly; full prompts belong in LangSmith/Logfire, not the cost table.

---

## Recommended starter library set

```toml
# pyproject.toml fragment
[project.dependencies]
python = ">=3.11,<3.13"
fastapi = "^0.115"
uvicorn = {version = "^0.32", extras = ["standard"]}
openai = "^1.55"
pydantic-ai = "^0.0.14"             # has OpenRouterModel
httpx = "^0.27"
asyncpg = "^0.30"
aiolimiter = "^1.2"
tenacity = "^9.0"
langsmith = "^0.2"                  # wrap_openai + @traceable
pyyaml = "^6.0"
# optional / alternates:
# logfire = "^2.0"                  # OTel-based observability
# langfuse = "^2.50"                # self-host alt to LangSmith
```

Vendor `model_prices_and_context_window.json` from `BerriAI/litellm` as `app/llm/_pricing.json` for fallback cost computation. Refresh quarterly.

---

## Open verifications

These items should be confirmed by a small spike before production:

1. **OpenRouter `usage.cost` in streaming for every model.** Docs say it's universal in the last SSE chunk; the LiteLLM bug report (#16021) shows at least one path where it disappears. Verify against our top 5 models with `stream=True`.
2. **Pydantic AI `OpenRouterModel` honours `extra_body` fallback list.** `OpenRouterModelSettings.openrouter_models` should map to `extra_body.models`. Test by killing the primary's API key and confirming fallback fires.
3. **Provider pinning slugs.** Confirm exact slugs for `anthropic` (direct) vs `amazon-bedrock` vs `google-vertex/us-east5`. Slugs in the docs are case-sensitive and have changed historically.
4. **`AsyncLimiter` behaviour at the boundary of the time window.** Leaky vs token-bucket distinction matters at burst — verify request 601 in a 60s window blocks until ~1s into the next window.
5. **`tenacity` + httpx + AsyncOpenAI** does not leak HTTP connections on retried streams (see openai-python issue #763). For non-streaming this is fine.
6. **LangSmith sampling.** Confirm `LANGSMITH_SAMPLING_RATE` is honored by `wrap_openai` (vs only `@traceable`). If not, gate `wrap_openai` calls behind a sampling decision yourself.
7. **`@traceable` interaction with `asyncio.Semaphore` / `aiolimiter`.** Spans must close even if `RuntimeError` raises. Test with a forced `KillSwitchOpenError`.
8. **Cost cap enforcement timing.** `hard_cost_cap_usd` triggers *after* the call (the cost is known only after). For pre-flight enforcement we need a token-count estimate (`tiktoken` for OpenAI models, `anthropic`'s `count_tokens` API for Claude). Decide whether pre-flight estimation is worth the dependency.
9. **Embedding usage shape** at OpenRouter (`/embeddings` endpoint). Confirm `usage.prompt_tokens` is populated for `openai/text-embedding-3-*` and `google/gemini-embedding-001`.
10. **FastAPI lifespan ordering.** `LlmRouter` must be created after `asyncpg.Pool`, before routes mount. Use `@asynccontextmanager` lifespan.

---

## Sources

- [OpenRouter Usage Accounting docs](https://openrouter.ai/docs/use-cases/usage-accounting)
- [OpenRouter Model Fallbacks docs](https://openrouter.ai/docs/guides/routing/model-fallbacks)
- [OpenRouter Provider Routing docs](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter API Streaming docs](https://openrouter.ai/docs/api/reference/streaming)
- [OpenRouter Embeddings API docs](https://openrouter.ai/docs/api/reference/embeddings)
- [Pydantic AI OpenRouter model API](https://ai.pydantic.dev/api/models/openrouter/)
- [Pydantic AI OpenRouter integration page](https://openrouter.ai/docs/guides/community/pydantic-ai)
- [LangSmith Tracing Quickstart](https://docs.langchain.com/langsmith/observability-quickstart)
- [`langsmith` PyPI package](https://pypi.org/project/langsmith/)
- [Tenacity docs](https://tenacity.readthedocs.io/)
- [OpenAI Cookbook — How to handle rate limits](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
- [aiolimiter docs](https://aiolimiter.readthedocs.io/)
- [LiteLLM OpenRouter provider docs](https://docs.litellm.ai/docs/providers/openrouter)
- [LiteLLM streaming `cost` bug — issue #16021](https://github.com/BerriAI/litellm/issues/16021)
- [LiteLLM streaming `cost`/`is_byok` bug — issue #11626](https://github.com/BerriAI/litellm/issues/11626)
- [Tracking LLM Usage and Cost with LiteLLM + PostgreSQL (IBM, Nov 2025)](https://community.ibm.com/community/user/blogs/wendy-munoz/2025/11/18/tracking-llm-usage-and-cost-with-litellm-postgresq)
- [LLM Gateway Comparison 2026 — RelayPlane](https://relayplane.com/blog/llm-gateway-comparison-2026)
- [OpenRouter vs LiteLLM vs Portkey — ToolHalla 2026](https://toolhalla.ai/blog/openrouter-vs-litellm-vs-portkey-2026)
- [Pydantic AI Observability Pricing Comparison (Logfire vs LangSmith vs Langfuse vs Arize)](https://pydantic.dev/articles/ai-observability-pricing-comparison)
- [LangSmith vs Langfuse — Langfuse FAQ](https://langfuse.com/faq/all/langsmith-alternative)
- [LaunchDarkly + FastAPI kill switch pattern](https://launchdarkly.com/blog/fastapi-python-kill-switch-flag/)
- [Token-bucket rate limiting with FastAPI — freeCodeCamp](https://www.freecodecamp.org/news/token-bucket-rate-limiting-fastapi/)
- [TimescaleDB hierarchical continuous aggregates](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/hierarchical-continuous-aggregates/)
- [openai-python concurrency issue #1725](https://github.com/openai/openai-python/issues/1725)
- [openai-python streaming connection leak issue #763](https://github.com/openai/openai-python/issues/763)
- [How to Handle Concurrent OpenAI API Calls with Rate Limiting — Villoro](https://villoro.com/blog/async-openai-calls-rate-limiter/)
