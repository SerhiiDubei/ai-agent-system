"""Knowledge service — orchestration layer for N3.

Wires together: embed query → retrieve → rerank.
Agents use this (not retriever directly) so the embedding detail is hidden.
"""

from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.knowledge.etl import IngestResult, ingest_file, ingest_vault
from ai_agent_system.knowledge.reranker import CrossEncoder, RetrievalCandidate, rerank
from ai_agent_system.knowledge.retriever import retrieve

log = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 1536


class KnowledgeService:
    """Facade for all knowledge operations.

    Instantiated once at app startup, shared across requests.
    """

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        *,
        cross_encoder: CrossEncoder | None = None,
    ) -> None:
        self._client = openai_client
        self._cross_encoder = cross_encoder

    async def search(
        self,
        session: AsyncSession,
        query: str,
        *,
        parent_category: str | None = None,
        niche: str | None = None,
        kind: str | None = None,
        top_k: int = 8,
    ) -> list[RetrievalCandidate]:
        """Embed query → hybrid retrieve → rerank → return top_k results."""
        resp = await self._client.embeddings.create(
            model=EMBED_MODEL, input=[query], dimensions=EMBED_DIMS
        )
        query_embedding = resp.data[0].embedding

        candidates = await retrieve(
            session,
            query,
            query_embedding,
            parent_category=parent_category,
            niche=niche,
            kind=kind,
        )

        return await rerank(
            query,
            candidates,
            cross_encoder=self._cross_encoder,
            top_k=top_k,
        )

    async def ingest_file(
        self,
        session: AsyncSession,
        path: Path,
        vault_root: Path,
    ) -> IngestResult:
        return await ingest_file(session, self._client, path, vault_root)

    async def ingest_vault(
        self,
        session: AsyncSession,
        vault_root: Path,
    ) -> list[IngestResult]:
        return await ingest_vault(session, self._client, vault_root)
