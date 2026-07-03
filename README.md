# ai-agent-system

> Standalone Python multi-agent AI system for generating A/B-test hypotheses for lead-gen landing pages.
>
> **Domain:** home improvement (15+ subniches: walk-in tubs, roofing, flooring etc.) + dating + extensible
> **Stack:** Python 3.11 + FastAPI + LangGraph + Pydantic AI + pgvector + OpenRouter + Obsidian-as-knowledge-vault
> **Status:** 🚧 skeleton phase, research-first per node (10 nodes — see `research/`)

---

## What this does (eventual)

```
URL → Page Snapshot → Multi-Agent Review → Decision Engine → Hypothesis Spec
                                                              ↓
                                                     Human approval (Obsidian markdown)
                                                              ↓
                                                     Ship to A/B testing platform
                                                              ↓
                                                     Auto-summarize results → Learning
                                                              ↓
                                                     Knowledge Base updated → next decisions
```

10 architectural nodes:

| Node | Purpose |
|---|---|
| **N1** | Browser & Snapshot — Firecrawl + DOM/visual/asset extraction + PII sanitization |
| **N2** | Semantic Role Mapping — Vision LLM з Set-of-Mark technique |
| **N3** | Knowledge System — Obsidian → pgvector з authority hierarchy |
| **N4** | Marketing Context — AI-drafted personas/pain points/user flow |
| **N5** | Multi-Agent Orchestration — LangGraph + Pydantic AI |
| **N6** | Decision Engine — priority formula + ranked output |
| **N7** | Hypothesis Builder — structured spec → Obsidian markdown |
| **N8** | Auto Feedback Loop — experiment results → learning notes |
| **N9** | Benchmark Harness — model × operation comparison |
| **N10** | LLM Gateway — OpenRouter routing + cost tracking + kill-switch |

Per-node research lives у `research/N<X>_<name>.md`.

---

## Quick start

### Local dev (з docker-compose)

```bash
# 1. Setup
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY, INTERNAL_API_KEY, LANGSMITH_API_KEY

# 2. Up
make up         # docker compose up -d --build
make logs       # follow app logs

# 3. Health check
curl http://localhost:8001/health

# 4. Down
make down
```

### Local dev без Docker

```bash
# 1. Install
make install    # pip install -e ".[dev,benchmark]"

# 2. Postgres локально (з pgvector)
# або: docker run -d --name pg-local -p 5432:5432 \
#        -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16

# 3. Migrate
make migrate

# 4. Run
make dev        # uvicorn з reload
```

---

## Architecture

Eventually integrates з existing Java Spring Boot product (`growthbook-ai-demo`) via REST API. Until then — fully standalone.

```
┌──────────────────────────────────┐
│  This service (Python FastAPI)   │
│  Port 8001                       │
│                                  │
│  /api/v1/snapshots/build         │  ← N1 + N2
│  /api/v1/agents/run              │  ← N5 + N4 + N3
│  /api/v1/decisions/rank          │  ← N6
│  /api/v1/proposals/{id}/...      │  ← N7
│  /api/v1/learnings/draft         │  ← N8
│  /api/v1/benchmark/run           │  ← N9
│  /api/v1/admin/cost/*            │  ← N10
│  /health                         │
└──────────┬───────────────────────┘
           │
   ┌───────┼───────┬─────────────┐
   ▼       ▼       ▼             ▼
Postgres  Firecrawl  OpenRouter  Obsidian
+pgvector (Node)    (LLM)        vault (git)
(via SQLAlchemy)
```

---

## Project layout

```
ai-agent-system/
├── pyproject.toml           # deps + tool configs (ruff, mypy, pytest)
├── Dockerfile               # multi-stage build для FastAPI service
├── docker-compose.yml       # full local stack (Postgres + Firecrawl + app)
├── Makefile                 # dev shortcuts
├── .env.example             # all env vars documented
├── alembic.ini              # DB migration config
├── alembic/                 # DB migrations
│   ├── env.py
│   └── versions/
├── configs/
│   └── llm_routing.yml      # per-operation LLM model selection
├── src/
│   └── ai_agent_system/
│       ├── __init__.py
│       ├── main.py          # FastAPI entrypoint
│       ├── config.py        # Pydantic Settings
│       ├── auth.py          # internal API key check
│       ├── db/              # SQLAlchemy session + base + models
│       ├── llm/             # OpenRouter router + cost tracking — N10
│       ├── snapshot/        # N1 + N2
│       ├── knowledge/       # N3
│       ├── marketing/       # N4
│       ├── agents/          # N5
│       ├── decision/        # N6
│       ├── hypothesis/      # N7
│       ├── learnings/       # N8
│       ├── benchmark/       # N9
│       └── api/             # FastAPI routers (one per concern)
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/         # Testcontainers Postgres
│   └── agent_quality/       # Golden snapshot tests (post-N5 build)
├── research/                # 10 research files (N1-N10)
└── README.md
```

---

## Research-first methodology

Before writing node-specific code, we research existing solutions для each node. See [`research/`](./research/).

10 research files produced via parallel research agents (квітень 2026). Synthesis у [`research/00_RESEARCH_SUMMARY.md`](./research/00_RESEARCH_SUMMARY.md) (after all 10 complete).

**Rule R1:** for each node — find existing OSS / SaaS / готові libraries → use as primary or as inspiration → custom only де реально немає.

---

## Documentation

Full alignment pack lives у `../alignment/` (15 docs covering decisions, validation, integration, sprint plan, user tasks). For solo dev / decision context only — not required reading.

For team/devs:
- [`../DEV_INTEGRATION_BRIEF.md`](../DEV_INTEGRATION_BRIEF.md) — самодостатній brief для дискусії з командою
- [`../alignment/14_SPRINT_PLAN.md`](../alignment/14_SPRINT_PLAN.md) — full sprint planning з QA gates + USER ACTION POINTS

---

## License

Proprietary. Internal use only.
