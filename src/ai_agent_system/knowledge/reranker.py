"""Post-retrieval reranker — N3.

Applies the final scoring blend over RRF candidates:
    final_score = α·semantic + β·authority + γ·freshness

Per N3 research:
- Start WITHOUT a cross-encoder (add bge-reranker-v2-m3 self-hosted when
  retrieval@10 plateaus). The blend alone is usually sufficient for v1.
- Authority weight belongs HERE (at re-rank), NOT in the vector space.
- LLM-reported confidence is uncalibrated — trust authority_tier + freshness
  as objective signals instead.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from ai_agent_system.knowledge.retriever import RetrievalCandidate


# ── Scoring weights — tunable ─────────────────────────────────────────
#
# α (ALPHA): weight on semantic/RRF score
#            Higher → retrieval relevance matters more
#
# β (BETA):  weight on authority tier
#            Higher → Tier 1 (our own A/B tests) dominate over GoodUI imports
#
# γ (GAMMA): weight on freshness (exponential decay with 180-day half-life)
#            Higher → recent notes rank above older ones
#
# Constraint: α + β + γ should sum close to 1.0 (they're normalised internally).
#
# N3 research starting point: α=0.55, β=0.30, γ=0.15
# — prioritises authority since our seed corpus is small and Tier 1 results
#   (real test outcomes) should dominate Tier 3 GoodUI imports even at lower
#   semantic similarity.
#
# TODO: after you've run the system for a few weeks and have 20+ approved
# patterns, run a retrieval eval (ragas or manual) and recalibrate these.
ALPHA: float = 0.55  # semantic / RRF relevance
BETA: float = 0.30   # authority tier
GAMMA: float = 0.15  # freshness

FRESHNESS_HALF_LIFE_DAYS: float = 180.0


@runtime_checkable
class CrossEncoder(Protocol):
    """Optional cross-encoder reranker protocol.

    Implement this to swap in bge-reranker-v2-m3 or Cohere Rerank.
    The `score` method returns one float per (query, text) pair.
    """

    async def score(self, query: str, texts: list[str]) -> list[float]: ...


def _freshness(age_days: float, half_life: float = FRESHNESS_HALF_LIFE_DAYS) -> float:
    """Exponential decay: 1.0 at age=0, 0.5 at age=half_life."""
    return math.exp(-age_days / half_life)


def _blend(c: RetrievalCandidate, ce_score: float | None = None) -> float:
    """Compute final_score for a single candidate.

    If a cross-encoder score is provided (min-max normalised to [0,1]),
    it replaces rrf_norm as the semantic signal.
    """
    semantic = ce_score if ce_score is not None else c.rrf_norm
    return ALPHA * semantic + BETA * c.authority_weight + GAMMA * _freshness(c.age_days)


async def rerank(
    query: str,
    candidates: list[RetrievalCandidate],
    *,
    cross_encoder: CrossEncoder | None = None,
    top_k: int = 8,
) -> list[RetrievalCandidate]:
    """Apply authority+freshness blend and optional cross-encoder reranking.

    Args:
        query: Original user query (passed to cross-encoder if provided).
        candidates: Output from retriever.retrieve() — sorted by rrf_norm.
        cross_encoder: Optional cross-encoder. If None, uses RRF score directly.
        top_k: Final count of results returned.

    Returns:
        Top-k candidates sorted by final_score descending.
    """
    if not candidates:
        return []

    ce_scores: list[float | None] = [None] * len(candidates)

    if cross_encoder is not None:
        raw = await cross_encoder.score(query, [c.text for c in candidates])
        if raw:
            lo, hi = min(raw), max(raw)
            span = (hi - lo) or 1.0
            ce_scores = [(s - lo) / span for s in raw]

    for candidate, ce_score in zip(candidates, ce_scores):
        candidate.final_score = _blend(candidate, ce_score)

    candidates.sort(key=lambda c: c.final_score, reverse=True)
    return candidates[:top_k]


class BgeReranker:
    """Self-hosted bge-reranker-v2-m3 via the `rerankers` library.

    Lazy-loaded: model downloads on first use (~560MB). Run in executor
    because the underlying library is synchronous.

    Install: pip install rerankers[transformers]
    """

    def __init__(self) -> None:
        self._model = None  # lazy init

    def _load(self):
        if self._model is None:
            from rerankers import Reranker  # type: ignore[import]

            self._model = Reranker("bge-reranker-v2-m3", model_type="cross-encoder")
        return self._model

    async def score(self, query: str, texts: list[str]) -> list[float]:
        import asyncio

        model = self._load()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: model.rank(query=query, docs=texts)
        )
        return [r.score for r in result.results]
