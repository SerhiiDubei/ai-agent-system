# Node N3 — Knowledge System Research

> Scope: Obsidian vault (separate git repo) → ETL → pgvector chunks (authority-tiered) → hybrid retrieval (vector + keyword + RRF) → optional cross-encoder rerank. Plus seed import (GoodUI, Growth.Design).
> Stack lock: Python 3.11, FastAPI, LangGraph, Pydantic AI, pgvector, OpenRouter, text-embedding-3-small @ 1536 dims, HNSW (m=16, ef_construction=64), per-H2 chunking, hash-diff ETL, watchdog + cron + git post-receive.
> Output language: English. Date of research: 2026-04-27.

---

## TL;DR

- **Build, don't buy.** None of LightRAG / Khoj / Mem0 / Cognee is a drop-in replacement for what we need: Obsidian-as-SoT + authority-weighted retrieval + tight integration with our LangGraph hypothesis-generation pipeline. They're worth studying, not adopting wholesale. Cognee is the closest "framework" alternative and is the right reference if we ever decide to add a graph layer.
- **Skip LightRAG for v1.** It's excellent at multi-hop QA over messy text but the graph extraction step requires a 32B+ LLM and meaningfully inflates indexing cost. At our 5K–100K chunk scale with high-quality, already-structured Obsidian notes (each note IS a curated entity), naive pgvector + RRF + rerank gives 80% of the lift at 10% of the complexity. Revisit when we have ≥50K chunks and observe multi-hop retrieval failures.
- **Hybrid search = pgvector + tsvector + RRF (k=60).** This is the 2026 consensus pattern and lifts retrieval precision from ~62% (pure vector) to ~84% in published benchmarks. Use `pg_trgm` only as a third leg for fuzzy short-string matches (URLs, brand names) — not as a primary search modality.
- **Authority weighting belongs at re-rank, not index.** Store `authority_tier` and `authority_weight` (1.0/0.7/0.4) as columns. After RRF candidate generation, apply a multiplicative blend `final = α·rerank_score + β·authority_weight + γ·freshness` (start with α=0.7, β=0.2, γ=0.1). This avoids polluting the embedding space and lets us tune weights per-niche without re-indexing.
- **Re-ranker: start without one, add `bge-reranker-v2-m3` self-hosted when retrieval@10 plateaus.** Cohere Rerank gives best quality (~0.735 nDCG@10) but adds an external dependency and per-call cost. For our scale (≤100K chunks, ≤500 queries/day) the latency win from a managed reranker is not worth the lock-in.
- **Embedding: stay on `text-embedding-3-small` for v1.** Voyage 3.5 / 4-lite are competitive at the same $0.02/MTok price and slightly better on retrieval, but the migration cost (re-embed 5K–100K chunks + dual-column window) is non-trivial. Lock in the parallel-column migration pattern NOW so the swap is cheap when we want it.
- **Skip Smart Connections MCP.** Its 384-dim `bge-micro-v2` embeddings are incompatible with our 1536-dim space, the index lives inside the Obsidian app process, and we'd have two embedding models to keep in sync. Our own ETL into pgvector is strictly better for agent integration.
- **GoodUI seeding: manual + light scrape.** Patterns are paywalled past the first ~10 of 141; full test data (610 tests) is members-only. Scraping is a TOS gray area and likely returns mostly headers. Better path: pay for one month of membership, export manually to markdown templates, classify into Tier 3, done. Estimated effort: 1 person-day for 141 patterns.

---

## Top 5 existing solutions (and why we don't adopt them wholesale)

### 1. LightRAG (HKUDS, EMNLP 2025)
**What it is.** Graph-augmented RAG. Indexes documents by extracting entities + relationships into a knowledge graph, then uses dual-level retrieval (low-level for specific entities, high-level for themes). RAGAS scores: Faithfulness 0.905, Context Recall 1.000.
**Storage.** Supports PostgreSQL (with pgvector), Neo4j, MongoDB, OpenSearch.
**Why not now.** (a) Recommended LLM is ≥32B params with ≥32KB context — that's expensive on every ingest. (b) Graph extraction step adds 5–10× indexing latency vs naive embedding. (c) Our notes are already curated entities; we'd be paying to re-derive structure we already have. (d) Setup wizard is improving but still meaningful integration work.
**Concrete advantage we'd miss.** Multi-hop reasoning ("which patterns have been tested in pricing pages AND increased conversion AND are mobile-friendly"). For v1 we can satisfy these via SQL joins on frontmatter metadata.
**Trigger to revisit.** ≥50K chunks AND we observe multi-hop retrieval failure rate >15% in eval set.

### 2. Cognee
**What it is.** Memory pipeline: ingestion → structuring (vector + graph) → recall. Closest to "managed framework" alternative for our stack.
**Strengths.** Strong on multi-hop reasoning (best DeepEval scores in their own benchmark vs Mem0/Graphiti/LightRAG). Production-ready connectors.
**Why not.** It's an opinionated framework — we lose the ability to encode our authority tiers natively, and we'd be wiring its graph schema to our domain. Also: 5–7 service dependencies.
**Use as.** Reference architecture for the eventual graph layer. Read their `cognee.tasks.repo` modules for chunking-as-pipeline patterns.

### 3. Mem0
**What it is.** Personal memory layer for agents. Optimized for high-throughput per-user state. Vector + filtering.
**Why not.** Wrong shape — Mem0 is for "what did this user say to me last Tuesday." We need "what does the corpus know about leadgen pricing patterns." Different problem.
**Use as.** N/A for N3. Possibly relevant for N5/N6 agent memory.

### 4. Khoj
**What it is.** Self-hosted personal AI that natively understands Obsidian, Notion, Markdown, PDFs. Has its own embedding pipeline + chat.
**Why not.** Khoj is a *product* (agent + chat UI). We need a *library/pipeline*. Embedding model isn't pluggable to the level we need, and its data lives in its own SQLite/Postgres schema we'd have to reverse-engineer.
**Use as.** Read `khoj/processor/content/markdown` for their per-section chunking. They handle Obsidian wikilinks well — worth borrowing.

### 5. Smart Connections (Obsidian plugin) + MCP servers
**What it is.** Local-first semantic search inside Obsidian using on-device `TaylorAI/bge-micro-v2` (384 dims). Multiple community MCP servers expose its embedding DB.
**Why not.**
- Embedding model mismatch: 384 dims vs our 1536. Cannot reuse vectors.
- Index lives in Obsidian's plugin process — Python agent has to either (a) shell out to MCP every call (slow, fragile) or (b) re-embed everything ourselves anyway.
- TaylorAI/bge-micro-v2 is meaningfully weaker than text-embedding-3-small on retrieval benchmarks.
**Use case where it WOULD help.** A human author working inside Obsidian who wants quick semantic search at write time. Keep installed for THAT, but don't build the agent on it.

---

## Code references worth studying

| Repo | What to steal |
|---|---|
| `HKUDS/LightRAG` (`lightrag/operate.py`) | Their dual-level retrieval prompts and entity-extraction templates |
| `cognee-ai/cognee` (`cognee/tasks/chunks/`) | Pipeline-as-DAG chunking — clean separation of parse / split / enrich |
| `khoj-ai/khoj` (`src/khoj/processor/content/markdown/markdown_to_entries.py`) | Obsidian-aware markdown→entries with wikilink handling |
| `AnswerDotAI/rerankers` | Unified API across Cohere/Jina/cross-encoder. Use this as our reranker abstraction so we can swap without rewriting |
| `verloop/md2chunks` | Context-enriched markdown chunking — good reference for our doc-title-prefix pattern |
| `messkan/rag-chunk` | CLI to benchmark chunking strategies on a corpus. Run this on our seed Obsidian vault to validate per-H2 vs alternatives empirically |
| `mfarragher/obsidiantools` | Pandas/NetworkX-based vault analytics. Good for vault audits and computing tag-graph metrics |
| `pgvector/pgvector` (README "Hybrid Search") | Canonical RRF SQL pattern |
| `tigerdata/pgai` (vectorizer) | If we want auto-embedding-on-insert via Postgres triggers — consider for v2 |
| `lepture/mistune` | Fastest CommonMark-compliant Python parser; what we should base the chunker on |

---

## Production case studies

- **Tiger Data (Timescale) blog series** — multiple posts documenting hybrid pgvector + BM25 + RRF in production. They publish concrete latency numbers (<10ms p95 at 1M vectors with HNSW m=16). Most directly applicable real-world reference.
- **Sourcegraph postgres text search blog** — long-form on tuning tsvector for code/text mix. Their conclusion: tsvector + pg_trgm covers 95% of fuzzy/exact needs without a dedicated search engine.
- **Google Cloud "Migrating embeddings without downtime" (Apr 2026)** — playbook we'll follow for our parallel-column pattern.
- **Cognee public benchmark (Aug 2025)** — Cognee, LightRAG, Graphiti, Mem0 head-to-head. Cognee wins multi-hop, all four lose to a properly-tuned hybrid pgvector setup on simple recall.

---

## Build vs buy verdict

**BUILD** the ETL pipeline and retrieval layer. **BORROW** specific patterns + libraries. Reasoning:

| Concern | Build cost | Buy cost | Verdict |
|---|---|---|---|
| Per-H2 chunking + frontmatter parsing | 1–2 days (mistune + python-frontmatter) | LightRAG/Cognee force their schema | Build |
| Embedding (OpenAI API) | Trivial | N/A | Build |
| Hybrid search (RRF SQL) | 1 day | Paradedb/pg_textsearch — adds extension | Build, reconsider extension if we want true BM25 |
| Authority tier weighting | 0.5 day | No tool does this natively | Build |
| Cross-encoder rerank | 1 day with `rerankers` lib | Cohere API: $1/1K rerank calls | Build with self-hosted bge-reranker; Cohere as fallback |
| Knowledge graph (multi-hop) | 1+ week (LightRAG-style) | LightRAG: integration + ops | DEFER — do not build OR buy until we see retrieval failures |
| File watcher | 0.5 day (watchdog) | N/A | Build |

Net: ~1 week of focused work for v1, vs 2–3 weeks integrating + bending a framework to our schema.

---

## Concrete patterns to copy

### A. Pydantic frontmatter validation model

```python
# ai_agent_system/knowledge/models.py
from datetime import date
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class AuthorityTier(int, Enum):
    REAL_TEST = 1       # weight 1.0  - our own A/B test outcomes
    USER_CURATED = 2    # weight 0.7  - hand-written notes by team
    EXTERNAL = 3        # weight 0.4  - GoodUI, Growth.Design imports

TIER_WEIGHTS = {1: 1.0, 2: 0.7, 3: 0.4}

class NoteFrontmatter(BaseModel):
    """Single source of truth for Obsidian frontmatter shape."""
    id: str = Field(..., pattern=r"^[a-z0-9_-]{6,}$")
    title: str = Field(..., min_length=3, max_length=200)
    kind: Literal["pattern", "test", "principle", "case_study", "research_note"]
    parent_category: Literal["home_improvement", "dating"]
    niches: list[str] = Field(default_factory=list, max_length=10)
    tags: list[str] = Field(default_factory=list)
    authority_tier: AuthorityTier
    source_url: str | None = None
    source_name: str | None = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)   # author-stated
    created: date
    updated: date
    metric_impact: dict[str, float] | None = None   # e.g. {"cvr_lift": 0.12}

    @field_validator("niches")
    @classmethod
    def _slugged(cls, v):
        for n in v:
            if not n.replace("_", "").isalnum():
                raise ValueError(f"niche must be slug: {n}")
        return v

    @property
    def authority_weight(self) -> float:
        return TIER_WEIGHTS[self.authority_tier]
```

### B. Complete ETL pipeline (parse → chunk → embed → upsert)

```python
# ai_agent_system/knowledge/etl.py
import hashlib
import asyncio
from pathlib import Path
import frontmatter
import mistune
from openai import AsyncOpenAI
import asyncpg

from .models import NoteFrontmatter, TIER_WEIGHTS

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 1536
MIN_CHUNK_TOKENS = 80     # below this, merge with neighbour
TARGET_CHUNK_TOKENS = 450
SHORT_DOC_OVERLAP = 60    # for docs < 500 tokens, use 60-token overlap

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _split_by_h2(md_body: str) -> list[tuple[str, str]]:
    """Returns list of (h2_heading, section_body). First section before any
    H2 is keyed by the doc title (passed in by caller)."""
    parser = mistune.create_markdown(renderer="ast")
    ast = parser(md_body)
    sections, current_heading, current_buf = [], None, []
    for node in ast:
        if node["type"] == "heading" and node["attrs"]["level"] == 2:
            if current_heading is not None or current_buf:
                sections.append((current_heading or "", _ast_to_md(current_buf)))
            current_heading = "".join(c["raw"] for c in node["children"] if "raw" in c)
            current_buf = []
        else:
            current_buf.append(node)
    sections.append((current_heading or "", _ast_to_md(current_buf)))
    return [(h, b.strip()) for h, b in sections if b.strip()]

def _ast_to_md(nodes) -> str:
    # Lightweight serializer; for production, use mistune's markdown renderer.
    out = []
    for n in nodes:
        if n["type"] == "paragraph":
            out.append("".join(c.get("raw", "") for c in n["children"]))
        elif n["type"] == "heading":
            out.append("#" * n["attrs"]["level"] + " " + "".join(c.get("raw","") for c in n["children"]))
        elif n["type"] == "block_code":
            out.append("```\n" + n["raw"] + "\n```")
        elif n["type"] == "list":
            for item in n["children"]:
                out.append("- " + "".join(c.get("raw","") for c in item.get("children", [])))
    return "\n\n".join(out)

def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)   # cheap heuristic; replace with tiktoken if needed

def chunk_note(fm: NoteFrontmatter, body: str) -> list[dict]:
    """Per-H2 chunking with doc-title prefix and overlap fallback for short docs."""
    sections = _split_by_h2(body)
    chunks = []
    full_doc_tokens = _approx_tokens(body)

    if full_doc_tokens < 500:
        # Short doc: emit single chunk, optionally with sliding window if we expect
        # query-side phrasing variance. Empirically a single chunk wins for <500 tok.
        text = f"{fm.title}\n\n{body.strip()}"
        chunks.append({"section": "", "text": text, "ord": 0})
        return chunks

    for i, (h2, body_text) in enumerate(sections):
        prefix = f"{fm.title}" + (f" / {h2}" if h2 else "")
        text = f"{prefix}\n\n{body_text}"
        # If a single H2 is huge, sliding-window split.
        if _approx_tokens(text) > TARGET_CHUNK_TOKENS * 1.6:
            words = body_text.split()
            window = TARGET_CHUNK_TOKENS * 4   # word-level approx
            stride = window - SHORT_DOC_OVERLAP * 4
            for j in range(0, len(words), stride):
                sub = " ".join(words[j:j + window])
                chunks.append({
                    "section": h2, "text": f"{prefix}\n\n{sub}", "ord": len(chunks),
                })
        else:
            chunks.append({"section": h2, "text": text, "ord": i})
    return chunks

async def embed_batch(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    resp = await client.embeddings.create(model=EMBED_MODEL, input=texts, dimensions=EMBED_DIMS)
    return [d.embedding for d in resp.data]

async def ingest_file(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    path: Path,
    vault_root: Path,
) -> dict:
    """Hash-diff ingest. Skips re-embedding if content unchanged.
    Returns {"chunks_added": int, "chunks_skipped": int, "skipped_file": bool}"""
    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)
    fm = NoteFrontmatter.model_validate(post.metadata)
    body = post.content

    rel_path = str(path.relative_to(vault_root)).replace("\\", "/")
    file_hash = _hash(raw)

    async with pool.acquire() as conn:
        existing_hash = await conn.fetchval(
            "SELECT file_hash FROM kb_documents WHERE rel_path = $1", rel_path
        )
        if existing_hash == file_hash:
            return {"chunks_added": 0, "chunks_skipped": 0, "skipped_file": True}

        # Compute chunks + per-chunk hash so we only re-embed deltas.
        new_chunks = chunk_note(fm, body)
        for c in new_chunks:
            c["chunk_hash"] = _hash(c["text"])

        existing = {
            r["chunk_hash"]: r["id"]
            for r in await conn.fetch(
                "SELECT id, chunk_hash FROM kb_chunks WHERE rel_path = $1", rel_path
            )
        }
        to_embed = [c for c in new_chunks if c["chunk_hash"] not in existing]

        if to_embed:
            # Batch by 96 to stay well under OpenAI's 2048 limit.
            for i in range(0, len(to_embed), 96):
                batch = to_embed[i:i + 96]
                vectors = await embed_batch(client, [c["text"] for c in batch])
                for c, v in zip(batch, vectors):
                    c["embedding"] = v

        # Transactional swap: delete old chunks for this file, insert all current.
        async with conn.transaction():
            await conn.execute("DELETE FROM kb_chunks WHERE rel_path = $1", rel_path)
            await conn.executemany(
                """
                INSERT INTO kb_chunks
                  (rel_path, doc_id, section, ord, text, chunk_hash,
                   authority_tier, authority_weight, parent_category, niches,
                   tags, kind, source_url, embedding, tsv)
                VALUES
                  ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::vector,
                   to_tsvector('english', $5))
                """,
                [
                    (
                        rel_path, fm.id, c["section"], c["ord"], c["text"], c["chunk_hash"],
                        int(fm.authority_tier), fm.authority_weight,
                        fm.parent_category, fm.niches, fm.tags, fm.kind, fm.source_url,
                        c.get("embedding") or _vector_for(existing[c["chunk_hash"]], conn),
                    )
                    for c in new_chunks
                ],
            )
            await conn.execute(
                """
                INSERT INTO kb_documents (rel_path, doc_id, file_hash, frontmatter, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, now())
                ON CONFLICT (rel_path) DO UPDATE
                  SET file_hash = EXCLUDED.file_hash,
                      frontmatter = EXCLUDED.frontmatter,
                      updated_at = now()
                """,
                rel_path, fm.id, file_hash, fm.model_dump_json(),
            )
    return {
        "chunks_added": len(to_embed),
        "chunks_skipped": len(new_chunks) - len(to_embed),
        "skipped_file": False,
    }
```

### C. Schema (DDL)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE kb_documents (
    rel_path     TEXT PRIMARY KEY,
    doc_id       TEXT NOT NULL,
    file_hash    TEXT NOT NULL,
    frontmatter  JSONB NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE kb_chunks (
    id               BIGSERIAL PRIMARY KEY,
    rel_path         TEXT NOT NULL REFERENCES kb_documents(rel_path) ON DELETE CASCADE,
    doc_id           TEXT NOT NULL,
    section          TEXT NOT NULL DEFAULT '',
    ord              INT NOT NULL,
    text             TEXT NOT NULL,
    chunk_hash       TEXT NOT NULL,
    authority_tier   SMALLINT NOT NULL,
    authority_weight REAL NOT NULL,
    parent_category  TEXT NOT NULL,
    niches           TEXT[] NOT NULL DEFAULT '{}',
    tags             TEXT[] NOT NULL DEFAULT '{}',
    kind             TEXT NOT NULL,
    source_url       TEXT,
    embedding        vector(1536) NOT NULL,
    tsv              tsvector NOT NULL,
    UNIQUE (rel_path, ord)
);

CREATE INDEX kb_chunks_embedding_hnsw
    ON kb_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX kb_chunks_tsv ON kb_chunks USING gin (tsv);
CREATE INDEX kb_chunks_text_trgm ON kb_chunks USING gin (text gin_trgm_ops);
CREATE INDEX kb_chunks_niches ON kb_chunks USING gin (niches);
CREATE INDEX kb_chunks_tags ON kb_chunks USING gin (tags);
CREATE INDEX kb_chunks_filters ON kb_chunks (parent_category, kind, authority_tier);
```

### D. Hybrid search SQL with RRF + authority blend

```sql
-- Parameters injected by application:
--   :q_text       (text query)
--   :q_vec        (embedding of query, vector(1536))
--   :niche        (TEXT, optional filter)
--   :parent_cat   (TEXT, optional filter)
--   :k_each       (int, candidates per leg, e.g. 60)
--   :k_final      (int, results returned, e.g. 30)
--   :rrf_k        (int, RRF constant, default 60)
--   :alpha        (float, similarity weight, 0.7)
--   :beta         (float, authority weight, 0.2)
--   :gamma        (float, freshness weight, 0.1)

WITH params AS (
    SELECT :rrf_k::int AS rrf_k,
           :alpha::float AS alpha,
           :beta::float AS beta,
           :gamma::float AS gamma
),
filtered AS (
    SELECT *
    FROM kb_chunks
    WHERE (:parent_cat IS NULL OR parent_category = :parent_cat)
      AND (:niche IS NULL OR :niche = ANY(niches))
),
vec AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> :q_vec) AS rank,
           1 - (embedding <=> :q_vec) AS sim
    FROM filtered
    ORDER BY embedding <=> :q_vec
    LIMIT :k_each
),
fts AS (
    SELECT id,
           ROW_NUMBER() OVER (
               ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', :q_text)) DESC
           ) AS rank,
           ts_rank_cd(tsv, plainto_tsquery('english', :q_text)) AS score
    FROM filtered
    WHERE tsv @@ plainto_tsquery('english', :q_text)
    LIMIT :k_each
),
trg AS (
    -- Optional third leg: catches part numbers, brand strings, exact phrases
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY similarity(text, :q_text) DESC) AS rank
    FROM filtered
    WHERE text % :q_text
    ORDER BY similarity(text, :q_text) DESC
    LIMIT :k_each
),
fused AS (
    SELECT id,
           SUM(1.0 / ((SELECT rrf_k FROM params) + rank)) AS rrf_score
    FROM (
        SELECT id, rank FROM vec
        UNION ALL SELECT id, rank FROM fts
        UNION ALL SELECT id, rank FROM trg
    ) u
    GROUP BY id
),
scored AS (
    SELECT c.id, c.rel_path, c.doc_id, c.section, c.text, c.kind,
           c.authority_tier, c.authority_weight, c.niches, c.tags,
           f.rrf_score,
           -- Normalize rrf_score across the result set into [0,1]
           f.rrf_score / NULLIF(MAX(f.rrf_score) OVER (), 0) AS rrf_norm,
           EXTRACT(EPOCH FROM (now() - d.updated_at)) AS age_seconds
    FROM fused f
    JOIN kb_chunks c ON c.id = f.id
    JOIN kb_documents d ON d.rel_path = c.rel_path
)
SELECT id, rel_path, doc_id, section, text, kind, authority_tier, niches, tags,
       (SELECT alpha FROM params) * rrf_norm
       + (SELECT beta  FROM params) * authority_weight
       + (SELECT gamma FROM params) * EXP(-age_seconds / (180.0 * 86400)) AS final_score,
       rrf_norm, authority_weight
FROM scored
ORDER BY final_score DESC
LIMIT :k_final;
```

### E. Authority-weighted re-rank (post-retrieval, with optional cross-encoder)

```python
# ai_agent_system/knowledge/rerank.py
from dataclasses import dataclass
from typing import Protocol
import math

@dataclass
class Candidate:
    id: int
    text: str
    rrf_norm: float           # from SQL [0,1]
    authority_weight: float   # 1.0 / 0.7 / 0.4
    age_days: float
    cross_encoder_score: float | None = None   # populated if reranker ran

class Reranker(Protocol):
    async def score(self, query: str, texts: list[str]) -> list[float]: ...

# Concrete: bge-reranker-v2-m3 via `rerankers` lib. Lazy-init.
class BgeReranker:
    def __init__(self):
        from rerankers import Reranker as RR
        self._r = RR("bge-reranker-v2-m3", model_type="cross-encoder")
    async def score(self, query, texts):
        # rerankers lib is sync; offload.
        import asyncio
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: self._r.rank(query=query, docs=texts)
        )
        return [r.score for r in result.results]

def freshness(age_days: float, half_life_days: float = 180.0) -> float:
    return math.exp(-age_days / half_life_days)

async def rerank(
    query: str,
    candidates: list[Candidate],
    reranker: Reranker | None = None,
    alpha: float = 0.55,   # semantic
    beta:  float = 0.30,   # authority
    gamma: float = 0.15,   # freshness
    top_k: int = 8,
) -> list[Candidate]:
    """If a cross-encoder is provided, replace rrf_norm with its score
    (min-max normalised) before blending. Otherwise blend on RRF score."""
    if reranker is not None:
        raw = await reranker.score(query, [c.text for c in candidates])
        if raw:
            lo, hi = min(raw), max(raw)
            span = (hi - lo) or 1.0
            for c, s in zip(candidates, raw):
                c.cross_encoder_score = (s - lo) / span

    def final(c: Candidate) -> float:
        sem = c.cross_encoder_score if c.cross_encoder_score is not None else c.rrf_norm
        return alpha * sem + beta * c.authority_weight + gamma * freshness(c.age_days)

    candidates.sort(key=final, reverse=True)
    return candidates[:top_k]
```

### F. Watchdog file watcher — debounced

```python
# ai_agent_system/knowledge/watcher.py
import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class VaultHandler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue, vault_root: Path, loop):
        self.queue, self.vault_root, self.loop = queue, vault_root, loop

    def _enqueue(self, path: str):
        p = Path(path)
        if p.suffix == ".md" and ".obsidian" not in p.parts and ".git" not in p.parts:
            asyncio.run_coroutine_threadsafe(self.queue.put(p), self.loop)

    def on_modified(self, event):  self._enqueue(event.src_path)
    def on_created(self, event):   self._enqueue(event.src_path)
    def on_moved(self, event):     self._enqueue(event.dest_path)

async def consume(queue: asyncio.Queue, ingest_fn, debounce_s: float = 1.5):
    """Coalesce bursts of writes (Obsidian saves several times in quick succession)."""
    pending: dict[Path, asyncio.TimerHandle] = {}
    loop = asyncio.get_running_loop()

    async def run(p: Path):
        pending.pop(p, None)
        try:
            await ingest_fn(p)
        except Exception as e:
            # log + continue; do NOT crash the watcher
            print(f"[watcher] ingest failed for {p}: {e}")

    while True:
        p: Path = await queue.get()
        if p in pending:
            pending[p].cancel()
        pending[p] = loop.call_later(debounce_s, lambda p=p: asyncio.create_task(run(p)))
```

### G. Zero-downtime embedding model migration (parallel column)

```sql
-- Step 1: add new column + index, leave old one live.
ALTER TABLE kb_chunks ADD COLUMN embedding_v2 vector(1024);  -- e.g. voyage-3-lite
CREATE INDEX CONCURRENTLY kb_chunks_embedding_v2_hnsw
    ON kb_chunks USING hnsw (embedding_v2 vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding_v2 IS NOT NULL;

-- Step 2: backfill in background batches (Python script).
-- Step 3: feature flag on read path: if EMBED_VERSION=v2, query embedding_v2.
-- Step 4: A/B compare on golden eval set; ramp to 100%.
-- Step 5: drop old column.
ALTER TABLE kb_chunks DROP COLUMN embedding;
ALTER TABLE kb_chunks RENAME COLUMN embedding_v2 TO embedding;
```

Application toggle:
```python
EMBED_VERSION = os.getenv("EMBED_VERSION", "v1")  # "v1" | "v2"
EMBED_COL = "embedding" if EMBED_VERSION == "v1" else "embedding_v2"
```

---

## Anti-patterns (do not do)

1. **Storing authority weight inside the embedding** (e.g. multiplying vector by tier weight). Pollutes the metric space and makes versioning impossible. Keep it as a column, blend at re-rank.
2. **Re-embedding the entire vault on every file save.** Use chunk-level hash diff. Most edits change one section; re-embedding 5 chunks vs 50 is the difference between $0.001 and $0.01 per save and 0.5s vs 5s.
3. **Using `LIMIT k` before RRF on each leg with k<50.** RRF is most useful when the legs disagree. Tiny per-leg candidate sets defeat the purpose. Use k_each=50–100.
4. **Choosing IVFFlat over HNSW for our scale.** IVFFlat is for >10M vectors with infrequent writes. We have ≤100K vectors and constant writes — HNSW wins on every dimension at this size.
5. **Indexing markdown frontmatter as part of the chunk body.** Frontmatter pollutes the embedding with structural noise (`tags: [a, b, c]`). Strip it; expose the structured fields as filterable columns.
6. **Building the knowledge graph "just in case."** Graph-RAG complexity (LightRAG/Cognee/Graphiti) is justified ONLY when you observe actual multi-hop retrieval failures in eval. Until then it's premature.
7. **Tying the read path to Smart Connections' embedding DB.** Different embedding model + index lives in Obsidian's process. Migration nightmare.
8. **Putting code blocks in their own chunks.** Code blocks lose meaning without surrounding prose. Keep them with the H2 they belong to. If a chunk exceeds budget because of a huge code block, sliding-window the prose around it; never split mid-fence.
9. **Using `text-embedding-3-large` (3072 dims) "for safety."** ~3× the storage and HNSW build time, marginal recall improvement at our scale. Save it for v2 only if eval shows gain.
10. **Allowing arbitrary frontmatter shapes.** Validate with the Pydantic model on every ingest; reject the file (and surface the error in vault) rather than silently embedding garbage.
11. **Skipping the doc-title prefix on chunks.** This is the cheapest possible context-recovery trick (~15 tokens) and it materially helps cross-document retrieval. Always prefix.
12. **Trusting Obsidian Sync as the SoT.** Use git as the SoT, with Obsidian Git plugin pushing on a timer. Sync is for editing convenience, not source of truth.

---

## Recommended starter library set

```toml
# pyproject.toml additions for N3
[project.dependencies]
python-frontmatter = "^1.1"      # YAML frontmatter
mistune            = "^3.0"      # fastest CommonMark parser
watchdog           = "^4.0"      # file watcher
asyncpg            = "^0.30"     # async Postgres
pgvector           = "^0.3"      # Python-side vector helpers
openai             = "^1.40"     # embeddings
tiktoken           = "^0.7"      # accurate token counting (replace heuristic)
pydantic           = "^2.7"      # already in stack
rerankers          = "^0.5"      # unified reranker API (bge / cohere / jina)
httpx              = "^0.27"     # for any rerank API calls

# Optional, evaluate post-MVP:
# lightrag-hku    = "*"          # only if multi-hop graph RAG becomes needed
# obsidiantools   = "*"          # vault analytics / link graph audits

[project.optional-dependencies.eval]
ragas              = "^0.2"      # retrieval+generation eval
```

Do **not** install: LangChain, LlamaIndex (too much surface area for a pipeline this focused), Chroma/Qdrant/Weaviate clients (we have pgvector), Khoj.

---

## Open verifications (before we lock the design)

1. **Empirical chunk-strategy benchmark** — Run `messkan/rag-chunk` on a sample of 50 hand-curated notes with a held-out query set. Verify per-H2 + doc-title prefix beats the alternatives (fixed 512, semantic split). Block on this.
2. **OpenAI batch API** — Confirm we can use OpenAI's batch embedding endpoint (50% discount, 24h SLA) for the GoodUI/Growth.Design seed import. Real-time path stays on the synchronous endpoint.
3. **`pg_textsearch` (Tiger Data BM25 extension) eval** — If we want true BM25 (Block-Max WAND) instead of `tsvector`+`ts_rank_cd`, this is the cleanest install. Verify it's available in our managed Postgres tier (Supabase / RDS / Tiger Cloud) before committing.
4. **GoodUI TOS check** — Confirm scraping the public preview portion of patterns is permitted; alternatively budget for one month of membership ($-tier?) and manual export. Do NOT scrape paywalled content.
5. **Reranker latency budget** — Self-hosted bge-reranker-v2-m3 on CPU: target p95 <250ms for 30 candidates. If exceeded, decide between (a) GPU host, (b) Cohere Rerank, or (c) drop reranker and lean on RRF + authority blend only.
6. **HNSW `ef_search` tuning** — We've fixed `m=16, ef_construction=64`. The runtime knob `ef_search` (default 40) materially affects recall vs latency. Sweep 40/80/100/200 against eval set and lock per environment.
7. **Watcher reliability under Obsidian Sync** — Obsidian Sync writes via temp files + rename; verify watchdog catches `on_moved` consistently on Windows (project is on Win11). If flaky, prefer the polling observer.
8. **Multi-niche scaling** — Decide hybrid: `kind/parent_category/file.md` folder layout (2 levels max) + niche/tag in frontmatter only. Avoid `kind/parent/niche/file.md` (3 levels) — it locks files into a single niche; many of ours apply across niches.
9. **Embedding dim choice** — text-embedding-3-small supports `dimensions` parameter (Matryoshka). Test if 768 dims gives equivalent retrieval at half the storage. Could meaningfully reduce HNSW memory.
10. **Postgres version** — pgvector 0.7+ adds halfvec (float16) — 2× storage saving, negligible recall hit. Check our Postgres version supports it; consider for v2.

---

## Sources

- [HKUDS/LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [LightRAG paper (ACL Anthology, EMNLP 2025)](https://aclanthology.org/2025.findings-emnlp.568/)
- [Hybrid Search in PostgreSQL — ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Tiger Data: hybrid search Postgres BM25 + vector + RRF](https://www.tigerdata.com/blog/elasticsearchs-hybrid-search-now-in-postgres-bm25-vector-rrf)
- [Tiger Data: pg_textsearch BM25 announcement](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)
- [Jonathan Katz: hybrid search with pgvector](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)
- [Building Hybrid Search for RAG (dev.to lpossamai)](https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk)
- [Markaicode: production pgvector RAG with HNSW](https://markaicode.com/pgvector-rag-production/)
- [ZeroEntropy: ultimate reranking model guide 2025](https://zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025/)
- [AnswerDotAI/rerankers GitHub](https://github.com/AnswerDotAI/rerankers)
- [Cognee blog: AI memory benchmarking (Cognee, LightRAG, Graphiti, Mem0)](https://www.cognee.ai/blog/deep-dives/ai-memory-evals-0825)
- [Cognee vs Mem0 comparison (dasroot.net)](https://dasroot.net/posts/2025/12/cognee-vs-mem0-memory-layer-comparison-llm-agents/)
- [brianpetro/obsidian-smart-connections GitHub](https://github.com/brianpetro/obsidian-smart-connections)
- [smart-connections-mcp (msdanyg)](https://github.com/msdanyg/smart-connections-mcp)
- [Obsidian + AI: Smart Connections + MCP (3sztof.github.io)](https://3sztof.github.io/posts/obsidian-smart-connections-mcp/)
- [Voyage AI: voyage-3-large announcement](https://blog.voyageai.com/2025/01/07/voyage-3-large/)
- [Embedding Models 2026 comparison (pecollective)](https://pecollective.com/tools/text-embedding-models-compared/)
- [TokenMix: text embedding pricing 2026](https://tokenmix.ai/blog/text-embedding-models-comparison)
- [GoodUI patterns list](https://goodui.org/patterns/list/)
- [GoodUI tests](https://goodui.org/tests/)
- [Zero-Downtime Embedding Migration (dev.to humzakt)](https://dev.to/humzakt/zero-downtime-embedding-migration-switching-from-text-embedding-004-to-text-embedding-3-large-in-1292)
- [Google Cloud: migrating embeddings without downtime (Apr 2026)](https://medium.com/google-cloud/migrating-vector-embeddings-in-production-without-downtime-8a0464af6f55)
- [Best chunking strategies for RAG 2025 (Firecrawl)](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)
- [Document chunking 9 strategies tested (langcopilot)](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide)
- [Markdown-first semantics: frontmatter and RAG (Steakhouse)](https://blog.trysteakhouse.com/blog/markdown-first-semantics-frontmatter-rag-retrieval)
- [mistune GitHub](https://github.com/lepture/mistune)
- [marko GitHub](https://github.com/frostming/marko)
- [verloop/md2chunks](https://github.com/verloop/md2chunks)
- [messkan/rag-chunk](https://github.com/messkan/rag-chunk)
- [Crunchy Data: HNSW indexes with pgvector](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [Tembo: pgvector IVFFlat vs HNSW](https://www.tembo.io/blog/vector-indexes-in-pgvector)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Ollama: bge-m3](https://ollama.com/library/bge-m3)
- [Ollama: nomic-embed-text-v2-moe](https://ollama.com/library/nomic-embed-text-v2-moe)
- [Tiger Data: best open-source embedding model for RAG](https://www.tigerdata.com/blog/finding-the-best-open-source-embedding-model-for-rag)
- [Aapeli: postgres text search trigram vs full-text](https://www.aapelivuorinen.com/blog/2021/02/24/postgres-text-search/)
- [Micelclaw: hybrid search with RRF (pgvector + tsvector + KG)](https://micelclaw.com/blog/hybrid-search-rrf/)
- [obsidiantools (mfarragher)](https://github.com/mfarragher/obsidiantools)
- [Watchdog Python ETL pattern (dev.to)](https://dev.to/devasservice/mastering-file-system-monitoring-with-watchdog-in-python-483c)
- [Multi-criteria reranking (arxiv 2504.07104)](https://arxiv.org/html/2504.07104v1)
- [AI Search Reranking: trust, freshness, relevance (Poniak Times)](https://www.poniaktimes.com/ai-search-reranking-layer/)
- [Pinecone: rerankers and two-stage retrieval](https://www.pinecone.io/learn/series/rag/rerankers/)
