# 00 — Research Synthesis (cross-node)

> Synthesis of all 10 research files (N1-N10) — common patterns, locked decisions, divergences, and integration points.
> Written after all 10 parallel research agents completed (квітень 2026).

---

## Universal "build, don't buy" verdict

**8 of 10 nodes returned "build, don't buy"** — confirming the project's wedge is **integration + curation + niche-specific quality**, not framework innovation.

Buy-only: N1 (Firecrawl), N9 (`huggingface/screensuite` + VisualWebBench для vision evals).
Hybrid: N3 (build pipeline + borrow patterns from LightRAG), N5 (LangGraph/Pydantic AI as base).
Pure build: N2, N4, N6, N7, N8, N10.

---

## Locked decisions (confirmed by ≥1 research, no contradictions)

### Stack core

| Layer | Locked choice | Source | Why |
|---|---|---|---|
| Python | 3.11+ | All nodes | LangGraph 1.0+ requires it, Pydantic AI v2 needs it |
| Web | FastAPI 0.115+ + uvicorn standard | All | Industry default for async Python AI services |
| Validation | Pydantic v2.5+ | All | Type-safe everything |
| Settings | pydantic-settings v2.5+ | N5, N7 | Cleaner than envvar reads |
| ORM | SQLAlchemy 2.0+ async | N3, N5, N10 | Native async, type-friendly |
| DB driver | psycopg3 (`psycopg[binary]`) | N3 | Modern, supports async natively |
| Migrations | Alembic for standalone phase | N3, N5 | Industry standard. **NB:** when integrated з Java, Java Flyway owns; Alembic deprecated then |
| Vector | pgvector (Postgres extension) | N3 | One less service. HNSW index, m=16, ef_construction=64 |
| Embeddings | `openai/text-embedding-3-small` 1536d | N3 | Voyage/local marginal benefit, migration not worth у v1 |

### LLM gateway

| Decision | Source | Detail |
|---|---|---|
| **SKIP LiteLLM** | N10 (strong) | Single-provider through OpenRouter does NOT justify Postgres+Redis+proxy stack. Known bug #16021 — usage.cost dropped on streaming through proxy |
| Use bare `openai.AsyncOpenAI` з `base_url` override | N10, N5 | ~300 LOC custom `LlmRouter`. Per-operation routing via YAML |
| OpenRouter native fallbacks via `extra_body.models` | N10 | Don't reinvent |
| Provider pinning via `extra_body.provider.order` + `allow_fallbacks: False` | N10 | Use коли benchmark показав specific provider quality |
| `usage.cost` ALWAYS returned in last SSE chunk (2026) | N10 | `stream_options.include_usage` is deprecated no-op |
| Tenacity retries ONLY for `APIConnectionError`/`APITimeoutError` | N10 | Don't double-handle 429s — OpenRouter does fallback |
| Pydantic AI: `OpenRouterProvider(openai_client=router.client)` | N10 | Shared client → unified semaphore + tracing + cost sink |
| Cost sink: hook `result.usage()` after `agent.run()` | N10 | Pydantic AI doesn't auto-call sink |
| `llm_calls` row per call + daily rollup `ON CONFLICT DO UPDATE` | N10 | Schema in research file |
| Kill-switch: Postgres bool з 5s TTL cache; reject new only, NEVER cancel in-flight | N10 | Avoid corrupted agent state |

### Browser & extraction (N1)

| Decision | Detail |
|---|---|
| `firecrawl-py` v4.23+ | Verified PyPI квітень 2026, `mobile: true`, full-page screenshots, `actions` array |
| Mobile + desktop = **2 parallel calls** | NOT viewport-switch. 2× cost, 100% reliability gain. Per N1 |
| Presidio over scrubadub | scrubadub dead (no PyPI release 12+ months) |
| `s0md3v/wappalyzer-next` (PyPI: `wappalyzer`) | Other Wappalyzer Python wrappers archived/unmaintained |
| selectolax з Lexbor backend | 5-30× faster than BeautifulSoup для auxiliary HTML parsing |
| **PRESERVE_ON_PAGE allowlist для PII** | **Critical:** phone/email на lead-gen LP — це **продукт**, не PII. Scrub only form values, query strings, console logs |
| Stealth (Camoufox/Patchright) — escape hatch only | Lead-gen LPs рідко мають aggressive bot protection |

### Semantic role mapping (N2)

| Decision | Detail |
|---|---|
| **Set-of-Mark (SoM) technique** is the #1 leverage pattern | Microsoft arXiv 2310.11441. Derive bboxes from DOM (`getBoundingClientRect`), overlay numbered badges на screenshot, LLM labels by `mark_id` (NOT coordinates) |
| **Hybrid DOM + vision crushes pure vision** | Skyvern-style ~85% on WebGames vs vision-only 18-39% (OmniParser v2: 39.5%) |
| **Never let LLM predict pixel coordinates** | #1 hallucination source. Always derive from DOM |
| Stack: OmniParser v2 (optional pre-detector) → Pydantic AI → Claude Sonnet 4.x via OpenRouter | GPT-4o cross-check, Opus arbitrator only on disagreements |
| Per-snapshot cost: ~$0.02-0.06 | Well below $0.20-0.50 budget. Headroom для multi-pass |
| **Enforce taxonomy invariants in Pydantic, NOT prompt** | `@model_validator` to demote duplicate `primary_cta` by confidence. Same для `hero_image` |
| Treat LLM-reported `confidence` as **uncalibrated** | Until you fit isotonic regression on labeled sample |

### Knowledge system (N3)

| Decision | Detail |
|---|---|
| **Skip LightRAG/Cognee/Khoj/Mem0 for v1** | None fits cleanly з Obsidian-as-SoT + custom authority tiers + LangGraph. Build pipeline ~1 week, borrow patterns. Revisit LightRAG only if multi-hop failures emerge >50K chunks |
| Hybrid search = pgvector + tsvector + RRF (k=60) + optional pg_trgm 3rd leg | Published benchmarks: ~62% → ~84% precision lift |
| Authority weighting at **re-rank, NOT in embedding** | Multiplying weights into vectors kills versioning. Store `authority_tier` (1/2/3) + `authority_weight` (1.0/0.7/0.4) as columns. Blend: `final = α·semantic + β·authority + γ·freshness` (start 0.55/0.30/0.15) |
| **Lock parallel-column embedding migration NOW** | DDL provided у N3 file. Allows future swap (text-embedding-3-small → Voyage / bge-m3) as feature-flag flip, not re-architecture |
| Skip Smart Connections MCP integration | 384-dim bge-micro-v2 incompatible з 1536-dim space, index lives в Obsidian process |
| GoodUI seeding: pay 1 month membership + manual export | Don't scrape paywalled content (~1 person-day) |
| Per-H2 chunking з doc title prefix | NOT sliding window для authored markdown |

### Marketing context (N4)

| Decision | Detail |
|---|---|
| **Multi-stage > single-shot:** `persona_drafter` → `sanity_judge` | Both на gpt-4o-mini, total cost ~$0.001-0.005 per draft. Retry up to 2x on judge fail |
| Schema is hardest part | Discriminated union для `ChannelProfile` (Meta/Google/TikTok/Snapchat distinct fields), typed `PainPoint` з platitude-rejecting validator, JTBD `primary_job` per persona, cross-field validators |
| **Senior + low-income demographics need explicit prompt rules** | Hardcode dual-persona rule для 55+ verticals (senior + adult-child decision_helper). Hardcode walk-in-tub buyers as `under_30k` or `30_60k` (NOT AI-default $60-100k). Hardcode US Special Ad Categories warning (housing/credit/employment block age+ZIP targeting на Meta) |
| Persona update workflow needs dedicated agent, NOT re-draft | DEEPER-inspired updater (Previous Preservation, Current Reflection, Future Advancement) merges + increments version |

### Multi-agent orchestration (N5)

| Decision | Detail |
|---|---|
| **Skip supervisor for MVP** — flat fan-out / fan-in | Deterministic edges + `Annotated[list, add]` reducers. Beats supervisor on latency, cost, debug. Promote to supervisor when Round 2 (Cross-Review) ships |
| **LangGraph 1.0+** (Oct 2025) — pin versions strictly | `langgraph-checkpoint-postgres>=2.0.21,<2.1`. CI step `.setup()` on every deploy. Breaking changes у minor bumps post-2.0.21 |
| **HITL via polling watcher, NOT blocking interrupt()** | `interrupt()` raises and unwinds. FastAPI background task polls `vault/approvals/*.md` for `status:` frontmatter changes → calls `graph.ainvoke(Command(resume={...}), config={"configurable": {"thread_id": ...}})`. Agent process and human loop decoupled — agent crash і resume still works |
| **Cost tracking dual-storage** | `Annotated[list[NodeCost], add]` reducer in graph state during run + flush to permanent `agent_run_costs` SQL table on graph completion. State-only loses on prune; DB-only fights LangGraph atomicity |
| **Schedule checkpoint-pruner cron from week 1** | #1 documented production fire ("ran out of disk"). `checkpoint_blobs` carries serialized state KB-by-KB |
| Reference repo: `coleam00/PydanticAI-Research-Agent` | Closest stylistic match для Pydantic AI side. Copy `agents/ tools/ models/ config/` layout + 500-line file cap |

### Decision Engine (N6)

| Decision | Detail |
|---|---|
| **Skip PyMCDM + scikit-criteria** | 30-line `priority_score()` + YAML config gives better explainability than wrapping libs |
| **Skip SHAP** | Для additive linear formulas, `weight_i × sub_score_i` IS Shapley value (mathematical fact). Build small `ScoreExplanation` dataclass that emits both natural-language ("Scored 8.2 because predicted impact contributed +2.4...") and waterfall-chart rows |
| Calibration plan: Beta-Binomial conjugate priors per `(industry × pattern_type)` bucket starting `Beta(2, 8)` | Shrinkage proportional to data sparsity (1.0 at 0 tests → 0.0 at ≥30 tests). Validate via Simulation-Based Calibration (Talts et al. 2018) BEFORE real outcomes |
| Defer AHP, bandits, Pareto-as-primary | AHP costs 15 pairwise comparisons per re-weight (unjustified for 6 weights), bandits — runtime traffic-allocation tool not hypothesis-selection (anti-pattern), Pareto-front = secondary trade-off badge alongside top-K, not the ranker |
| CRO-tool prior art opaque | AB Tasty EVI, Unbounce Smart Traffic, Mutiny hide ranking. PIE/ICE/PXL public formulas. **Our explainable breakdown = real differentiator** |

### Hypothesis builder (N7)

| Decision | Detail |
|---|---|
| Stack: Pydantic v2 + Jinja2 + python-frontmatter + python-statemachine + watchdog | ~12 transitive deps, all permissive licenses, ~300 LOC glue. Build, don't buy |
| **Two-file persistence per spec:** human `.md` + sibling `.spec.json` | Frontmatter owns `decision_status` + `review_note`, body is narrative. JSON is canonical machine state. Watcher diffs frontmatter; spec rehydrated from JSON. Sidesteps YAML pain з multi-line `reasoning` + nested `evidence` |
| `python-statemachine` (NOT `transitions`) | `transitions` monkey-patches everything. `python-statemachine` is class-based, hooks, type-friendly |
| Lifecycle: `pending → approved/rejected/modified → shipped/superseded` | `modify` spawns NEW spec via `superseded_by` — non-destructive (per dbt model-versioning playbook) |
| Watchdog gotchas confirmed | Obsidian on Windows fires 1 Created + 2-3 Modified per save. iCloud/Dropbox/OneDrive vaults need `PollingObserver`. **1.5s timestamp-debounce per file is safe minimum** |
| **Adopt GrowthBook field vocabulary** | `hypothesis`, `goal_metrics`, `secondary_metrics`, `guardrail_metrics`, `variations`. M14 handoff = flat field-mapping, not semantic translation. `HypothesisSpec` = superset з `change_level L1-L4`, `evidence`, `reasoning`, `risk_level` (fields GrowthBook doesn't natively model) |
| Bulk approval = Dataview-rendered index `.md` | No custom UI needed для MVP |

### Auto feedback loop (N8)

| Decision | Detail |
|---|---|
| **Trigger = HYBRID: webhook + reconciliation cron** | NOT webhook-only. GrowthBook retries 3 times з exp backoff; deploy during window kills loop. Webhook 99% fast; nightly poll catches 1% missed |
| **Templating > prompting для anti-hallucination** | Fixed Markdown template + strict JSON-schema response. LLM only fills typed slots (`statistical_interpretation`, `key_insights`, `needs_review_reasons`). **Numbers come MECHANICALLY from stats payload — LLM never invents a metric** |
| **Confidence is COMPUTED, not trusted** | `confidence = min(LLM self-rating, stats-derived band)` where stats band uses `p-value × min sample size × duration × SRM check`. Self-reported LLM confidence gameable; combination + red badges in vault index = practical "this draft might be wrong" signal |
| **Vault git: subprocess + system `git` wins для MVP** | GitPython adds 70 MB + leaks file handles на Windows. Dulwich для no-git environments only. Subprocess failures debuggable as CLI |
| **Brier scoring closes long-term loop** | Persist `predicted_confidence` + `outcome_for_brier` per resolved hypothesis. Weekly `system_calibration()` rolls into `meta_calibration_<week>.md`. ~30 resolutions = real overconfidence signal (most common failure mode per PredictionBook data) |

### Benchmark harness (N9)

| Decision | Detail |
|---|---|
| **Build thin Python harness ~600-900 LOC, NOT LangSmith/Helicone framework** | Our scope ~360-540 calls/run, $15-30 — too small to justify heavy framework |
| Promptfoo as YAML helper для prompt iteration | Formal benchmark = custom Python module wrapping OpenRouter directly |
| **OpenRouter `usage.cost` UNRELIABLE in streaming** | Documented LiteLLM bugs #11626, #16021. ALWAYS reconcile by re-querying `GET /api/v1/generation?id=<gen_id>` after call. Cross-check з `/credits` delta per run |
| **N=2-3 reps: median + bootstrap CIs + Mann-Whitney U, NOT t-test** | CLT does not hold at these sample sizes (Miller et al. 2026). Plot Pareto frontier, pick λ per operation rather than collapse to single composite |
| Quality scoring needs 30-50 example human-calibrated set per operation | Validate LLM judge before scaling. Mandate position-swap on pairwise judging (40% inconsistency rate documented для GPT-4-class judges). NEVER let candidate model judge itself (self-preference bias) |
| For N2 vision evaluation, lean on existing benchmark suites | `huggingface/screensuite` (most comprehensive 2026 GUI-agent suite) + `VisualWebBench` (1.5k human-curated web understanding instances). Don't roll vision eval set from scratch |

### LLM Gateway (N10)

Already covered above у "LLM gateway" section. Key additions:
- **Logfire ~40× cheaper than LangSmith** at 50M spans/month per Pydantic's published comparison. Alternative if cost matters
- Dual deep-link: set Postgres `trace_id` from `langsmith.get_current_run_tree().id` so every billing row links to LangSmith trace
- `wrap_openai(AsyncOpenAI(...))` is one line LangSmith setup

---

## Common patterns across nodes

### Pattern A — Pydantic models as primary contracts
Nodes N2, N4, N5, N6, N7, N10 all rely heavily on Pydantic v2 + Pydantic AI structured output. Pattern: define schema → enforce invariants з `@model_validator` → never trust LLM to follow prompt instructions about structure.

### Pattern B — DB-backed state, not in-memory
Nodes N5 (cost tracking), N7 (state machine + spec storage), N8 (Brier scores), N10 (cost sink) — all require persistent SQL tables. Single Postgres OK for all.

### Pattern C — File watcher як integration glue
Nodes N3 (Obsidian ETL), N5 (HITL approval), N7 (status changes), N8 (vault git push) — all use file watching as the human-in-the-loop interface. Single watchdog instance can serve multiple consumers.

### Pattern D — Author-time vs runtime separation
- **Author-time tools** (для humans): Obsidian + plugins, Smart Connections, Templater, Dataview
- **Runtime** (для agents): Python services, no Obsidian dependency
- Bridge = file watcher + git push/pull

### Pattern E — Confidence as derived, not reported
Nodes N2 (semantic mapping), N6 (decision ranking), N8 (learning drafts) — all warn against trusting LLM-reported confidence. Pattern: combine LLM rating з derived metric (isotonic regression, statistical band, agent agreement) before surfacing to user.

---

## Divergences / open questions

### O1 — LangSmith vs Logfire
N10 flagged Logfire ~40× cheaper at scale. N5 assumes LangSmith.
**Recommendation:** Start LangSmith (free tier), migrate to Logfire if traces > 50K/mo. Re-decide Sprint 5+.

### O2 — pg_textsearch / BM25 availability
N3 flagged "pg_textsearch BM25 availability в managed Postgres" як blocking verification.
**Action:** Verify before V9-equivalent migration. Falls back to tsvector + ts_rank_cd if pg_textsearch unavailable.

### O3 — Obsidian Sync vs git
N7 flagged: 1.5s debounce minimum, iCloud/Dropbox/OneDrive vaults need `PollingObserver`.
**Action:** Document as **git-only** in `13_USER_LEARNING_TASKS.md`. Forbid Obsidian Sync для production setup.

### O4 — Watchdog reliability under Windows + Obsidian
N7 flagged "Obsidian on Windows fires 1 Created + 2-3 Modified per save".
**Action:** Implement timestamp-debounce + de-dup logic from day 1.

### O5 — GoodUI scraping vs paid membership
N3 says "pay 1 month membership + manual export" instead of scrape paywalled. N4 confirms.
**Action:** Budget $30-50 для 1-month membership. Manual export 141 patterns + 610 tests as Tier 3 seed.

### O6 — OmniParser v2 для N2
N2 says "optional pre-detector". Hardware needs?
**Action:** Test OmniParser v2 on test server. If quality bump justifies infra, add. Otherwise skip.

---

## Concrete deps locked у `pyproject.toml`

Already committed у skeleton:

```toml
[project.dependencies]
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.5
pydantic-settings>=2.5
langgraph>=0.2.50         # (will pin to >=1.0,<2.0 коли LangGraph 1.0 stable verified)
pydantic-ai>=0.0.14
openai>=1.50              # з base_url override → OpenRouter (NOT LiteLLM per N10)
firecrawl-py>=4.23        # confirmed PyPI квітень 2026 (N1)
selectolax>=0.3.21        # Lexbor backend, 5-30× faster than BS4 (N1)
wappalyzer>=0.2           # s0md3v/wappalyzer-next (N1)
presidio-analyzer>=2.2    # PII (N1)
presidio-anonymizer>=2.2
python-frontmatter>=1.1
watchdog>=5.0
GitPython>=3.1            # ⚠️ N8 caution: 70MB + Windows file handle leaks. Consider subprocess git
pgvector>=0.3
sqlalchemy>=2.0
psycopg[binary]>=3.2
alembic>=1.13
httpx>=0.27
tenacity>=9.0             # ⚠️ N10: ONLY for connection/timeout errors, NOT 429s
aiolimiter>=1.1
langsmith>=0.1.140
loguru>=0.7
```

**Need to add post-research (in next dep update):**
- `python-statemachine` (N7 — NOT `transitions`)
- `Jinja2` (N7 — markdown templating)

**Need to consider adding:**
- `logfire` (alternative to LangSmith)
- `outlines` (constrained generation backup if Pydantic AI structured output insufficient)

**Considered but rejected:**
- ❌ `litellm` (N10 strong: skip, single-provider doesn't justify proxy stack + bug)
- ❌ `pymcdm`, `scikit-criteria` (N6: overkill для 6-criterion additive formula)
- ❌ `lightrag` (N3: doesn't fit our architecture, may revisit at >50K chunks)
- ❌ `khoj`, `mem0`, `cognee` (N3: skip, build patterns from these as inspiration only)
- ❌ `transitions` (N7: monkey-patches everything)
- ❌ `scrubadub` (N1: dead, no PyPI release 12+ months)
- ❌ Smart Connections MCP integration (N3: embedding model mismatch)

---

## Map: research findings → skeleton state

| Skeleton file | Research source | Status |
|---|---|---|
| `pyproject.toml` | All 10 — locked deps | ✅ Done |
| `Dockerfile` | N5 (FastAPI patterns) | ✅ Done |
| `docker-compose.yml` | N1 (Firecrawl official self-host stack) | ✅ Done |
| `.env.example` | N10 (env vars), N3, N1 | ✅ Done |
| `Makefile` | Standard | ✅ Done |
| `src/.../config.py` | N10 + all | ✅ Done |
| `src/.../auth.py` | N10 (shared secret) | ✅ Done |
| `src/.../main.py` | Skeleton FastAPI | ✅ Done (placeholders for routers) |
| `src/.../db/{base,session}.py` | N3, N5 | ✅ Done |
| `configs/llm_routing.yml` | N10 + N6 + N5 + N4 | ✅ Done (initial routing — refine post-Sprint 5.5 benchmark) |
| `alembic/{ini,env,script.mako}` | N3 | ✅ Done |
| `tests/{conftest,test_health}.py` | N5 (Testcontainers) | ✅ Done |
| `src/.../snapshot/` | N1 + N2 | 🟡 To-do — design phase |
| `src/.../knowledge/` | N3 | 🟡 To-do |
| `src/.../marketing/` | N4 | 🟡 To-do |
| `src/.../agents/` | N5 | 🟡 To-do |
| `src/.../decision/` | N6 | 🟡 To-do |
| `src/.../hypothesis/` | N7 | 🟡 To-do |
| `src/.../learnings/` | N8 | 🟡 To-do |
| `src/.../benchmark/` | N9 | 🟡 To-do |
| `src/.../llm/` | N10 | 🟡 To-do — first node to implement (foundation для всіх інших) |

---

## Recommended implementation order

Based on dependency graph + research findings:

1. **N10 LLM Gateway** — foundation. Без LlmRouter не можемо тестувати інші nodes. ~300 LOC.
2. **N3 Knowledge System** — foundation для context retrieval. ~1 week per N3.
3. **N1 Browser & Snapshot** — produces the data inputs. Firecrawl SDK = thin wrapper.
4. **N2 Semantic Role Mapping** — depends on N1 output, uses N10 for vision LLM. SoM technique implementation.
5. **N4 Marketing Context** — independent of pipeline, can be parallel. Multi-stage drafter→judge.
6. **N5 Multi-Agent Orchestration** — depends on N3 (knowledge), N4 (context), N10 (LLM). Agent Roster Design Session needed before this.
7. **N6 Decision Engine** — depends on N5 outputs.
8. **N7 Hypothesis Builder** — depends on N6 outputs. State machine + Markdown export.
9. **N8 Auto Feedback Loop** — depends on external system providing experiment results. Can be late.
10. **N9 Benchmark Harness** — independent. Run before N5 finalization (Sprint 5.5).

---

## Decision points що потребують тебе

Перед implementation — треба узгодити:

### D1 — Brief change у `pyproject.toml`
- Add `python-statemachine` and `Jinja2` (per N7)
- Consider replacing `GitPython` з subprocess pattern (per N8)
- LangGraph version pin tightening (`>=1.0,<2.0` коли verify 1.0 stable)

### D2 — GoodUI access
- Budget $30-50 для 1-month membership? (N3, N4 confirmed)
- OR: skip GoodUI seed completely, rely on hand-curated patterns?

### D3 — OmniParser v2 evaluation
- Add to test server для N2 evaluation? Або skip?

### D4 — LangSmith now, Logfire later confirmation
- OK plan: LangSmith free tier, switch to Logfire when traces > 50K/mo?

### D5 — Implementation order
- Approve N10 → N3 → N1 → N2 → N4 → N5 → N6 → N7 → N8/N9 sequence?
- Or different priority?

### D6 — Agent Roster Design Session timing
- Per N5: need this before implementing M5. Schedule before N5 implementation begins.
- Format: structured cards like Q&A phase, ~1-2 hours.

---

## What's next

**Skeleton complete.** Standalone project на `E:\Work Stuff\buggy\ai-agent-system\` ready to develop.

**To proceed:**
1. You answer D1-D6 above (5-10 хв)
2. We start per-node design + implementation, beginning з N10 LLM Gateway
3. Each node: ~1-2 sprints, з QA gates як у `alignment/14_SPRINT_PLAN.md` adapted

OR you can request:
- Deeper design phase per node (architecture docs first, then code)
- Different implementation order
- Dispatch additional research agents on specific gaps

Your call.
