"""Hybrid knowledge retrieval — N3.

Search strategy (per N3 research):
  1. Vector leg   — ANN cosine search via HNSW index
  2. FTS leg      — tsvector full-text search via GIN index
  3. Trigram leg  — pg_trgm fuzzy match (brand names, short queries)
  4. RRF fusion   — Reciprocal Rank Fusion with k=60 across all legs
  5. Blend        — α·similarity + β·authority + γ·freshness (tunable)

Anti-patterns avoided (per N3):
- k_each < 50 (RRF needs enough candidates to be useful — use 60)
- Authority weight in embedding space (kills versioning; use column blend)
- IVFFlat index (HNSW wins at our scale)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# ── RRF + blend defaults ──────────────────────────────────────────────
RRF_K = 60          # RRF constant — 60 is the canonical value (Robertson 2009)
K_EACH = 60         # candidates per search leg
K_FINAL = 30        # candidates returned to Python for rerank


_HYBRID_SQL = """
WITH filtered AS (
    SELECT *
    FROM kb_chunks
    WHERE (:parent_cat IS NULL OR parent_category = :parent_cat)
      AND (:niche      IS NULL OR :niche = ANY(niches))
      AND (:kind       IS NULL OR kind = :kind)
),
vec AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:q_vec AS vector)) AS rank,
           1 - (embedding <=> CAST(:q_vec AS vector))                         AS sim
    FROM filtered
    ORDER BY embedding <=> CAST(:q_vec AS vector)
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
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY similarity(text, :q_text) DESC) AS rank
    FROM filtered
    WHERE text % :q_text
    ORDER BY similarity(text, :q_text) DESC
    LIMIT :k_each
),
fused AS (
    SELECT id,
           SUM(1.0 / (:rrf_k + rank)) AS rrf_score
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
           f.rrf_score / NULLIF(MAX(f.rrf_score) OVER (), 0) AS rrf_norm,
           EXTRACT(EPOCH FROM (now() - d.updated_at)) / 86400.0  AS age_days
    FROM fused f
    JOIN kb_chunks   c ON c.id = f.id
    JOIN kb_documents d ON d.rel_path = c.rel_path
)
SELECT id, rel_path, doc_id, section, text, kind, authority_tier, authority_weight,
       niches, tags, rrf_norm, age_days
FROM scored
ORDER BY rrf_norm DESC
LIMIT :k_final
"""


@dataclass
class RetrievalCandidate:
    """Single chunk returned by the retriever, before Python-side reranking."""

    id: int
    rel_path: str
    doc_id: str
    section: str
    text: str
    kind: str
    authority_tier: int
    authority_weight: float
    niches: list[str]
    tags: list[str]
    rrf_norm: float           # RRF-fused score normalised to [0, 1]
    age_days: float
    final_score: float = field(default=0.0)   # filled by reranker


async def retrieve(
    session: AsyncSession,
    query: str,
    query_embedding: list[float],
    *,
    parent_category: str | None = None,
    niche: str | None = None,
    kind: str | None = None,
    top_k: int = K_FINAL,
    k_each: int = K_EACH,
    rrf_k: int = RRF_K,
) -> list[RetrievalCandidate]:
    """Hybrid retrieval from kb_chunks.

    Args:
        session: SQLAlchemy async session (read-only query, no commit needed).
        query: Natural language query for FTS + trigram legs.
        query_embedding: Pre-computed embedding for vector leg.
        parent_category: Optional filter ("home_improvement" | "dating").
        niche: Optional niche slug filter (e.g. "walk_in_tub").
        kind: Optional note type filter ("pattern" | "test" | ...).
        top_k: Final number of candidates to return (before Python reranking).

    Returns:
        List of RetrievalCandidate sorted by rrf_norm descending.
        The caller (service layer) runs reranking on top of this.
    """
    vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    params = {
        "q_text": query,
        "q_vec": vec_str,
        "parent_cat": parent_category,
        "niche": niche,
        "kind": kind,
        "k_each": k_each,
        "k_final": top_k,
        "rrf_k": rrf_k,
    }

    result = await session.execute(text(_HYBRID_SQL), params)
    rows = result.fetchall()

    candidates = [
        RetrievalCandidate(
            id=row.id,
            rel_path=row.rel_path,
            doc_id=row.doc_id,
            section=row.section,
            text=row.text,
            kind=row.kind,
            authority_tier=row.authority_tier,
            authority_weight=row.authority_weight,
            niches=list(row.niches) if row.niches else [],
            tags=list(row.tags) if row.tags else [],
            rrf_norm=float(row.rrf_norm or 0.0),
            age_days=float(row.age_days or 0.0),
        )
        for row in rows
    ]

    log.debug(
        "knowledge retriever: query=%r → %d candidates (parent_cat=%s niche=%s)",
        query[:60],
        len(candidates),
        parent_category,
        niche,
    )
    return candidates
