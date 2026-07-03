"""Knowledge ETL pipeline: Obsidian note → DB chunks — N3.

Per N3 research:
- Hash-diff at file level (skip entirely if unchanged)
- Hash-diff at chunk level (only re-embed changed chunks)
- Transactional delete-old + insert-new chunks (atomic swap)
- Batch embed: 96 texts per API call (well under OpenAI 2048 limit)
- tsv computed by DB: to_tsvector('english', text) in INSERT SQL
- Vector passed as string '[x,y,...]' for psycopg3/pgvector compat
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import frontmatter as python_frontmatter
from openai import AsyncOpenAI
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.knowledge.chunker import Chunk, chunk_note
from ai_agent_system.knowledge.models import NoteFrontmatter

log = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 1536
EMBED_BATCH_SIZE = 96  # well under OpenAI 2048 limit


@dataclass
class IngestResult:
    rel_path: str
    chunks_added: int
    chunks_reused: int
    skipped_file: bool        # True when file hash unchanged (nothing to do)
    validation_error: str | None = None


def _file_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _embed_batch(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    resp = await client.embeddings.create(
        model=EMBED_MODEL, input=texts, dimensions=EMBED_DIMS
    )
    return [item.embedding for item in resp.data]


def _vec_str(embedding: list[float]) -> str:
    """Format vector for PostgreSQL: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


async def ingest_file(
    session: AsyncSession,
    client: AsyncOpenAI,
    path: Path,
    vault_root: Path,
) -> IngestResult:
    """Hash-diff ingest of a single Obsidian note.

    Steps:
    1. Read + parse frontmatter (reject invalid)
    2. File-level hash check (skip if unchanged)
    3. Chunk the note
    4. Chunk-level hash check (reuse existing embeddings where possible)
    5. Embed only new/changed chunks in batches
    6. Transactional swap: delete old chunks, insert all current
    7. Upsert kb_documents row
    """
    raw = path.read_text(encoding="utf-8")
    rel_path = str(path.relative_to(vault_root)).replace("\\", "/")

    # ── Parse + validate frontmatter ──
    try:
        post = python_frontmatter.loads(raw)
        fm = NoteFrontmatter.model_validate(post.metadata)
    except (ValidationError, Exception) as exc:
        log.warning("knowledge ETL: validation error for %s: %s", rel_path, exc)
        return IngestResult(
            rel_path=rel_path,
            chunks_added=0,
            chunks_reused=0,
            skipped_file=False,
            validation_error=str(exc),
        )

    body = post.content
    file_hash = _file_hash(raw)

    # ── File-level hash check ──
    row = (
        await session.execute(
            text("SELECT file_hash FROM kb_documents WHERE rel_path = :p"),
            {"p": rel_path},
        )
    ).fetchone()

    if row and row[0] == file_hash:
        return IngestResult(
            rel_path=rel_path, chunks_added=0, chunks_reused=0, skipped_file=True
        )

    # ── Chunk ──
    chunks = chunk_note(fm, body)
    if not chunks:
        log.warning("knowledge ETL: no chunks produced for %s", rel_path)
        return IngestResult(
            rel_path=rel_path,
            chunks_added=0,
            chunks_reused=0,
            skipped_file=False,
        )

    # ── Chunk-level hash check — load existing chunk hashes ──
    existing_rows = (
        await session.execute(
            text("SELECT chunk_hash, embedding::text FROM kb_chunks WHERE rel_path = :p"),
            {"p": rel_path},
        )
    ).fetchall()
    existing: dict[str, str] = {r[0]: r[1] for r in existing_rows}

    # Separate: needs new embedding vs can reuse
    to_embed: list[Chunk] = []
    to_reuse: list[Chunk] = []
    for chunk in chunks:
        if chunk.chunk_hash in existing:
            # Reuse: set embedding from stored string (will be re-inserted below)
            to_reuse.append(chunk)
        else:
            to_embed.append(chunk)

    # ── Embed new/changed chunks in batches ──
    if to_embed:
        for i in range(0, len(to_embed), EMBED_BATCH_SIZE):
            batch = to_embed[i : i + EMBED_BATCH_SIZE]
            vectors = await _embed_batch(client, [c.text for c in batch])
            for chunk, vec in zip(batch, vectors):
                chunk.embedding = vec
        log.debug(
            "knowledge ETL: embedded %d new chunks for %s", len(to_embed), rel_path
        )

    # For reused chunks, retrieve their stored embeddings
    existing_embeddings: dict[str, str] = existing  # hash → vec string
    for chunk in to_reuse:
        # The embedding string from DB is already in '[x,y,...]' format
        chunk.embedding = existing_embeddings[chunk.chunk_hash]  # type: ignore[assignment]

    # ── Transactional swap ──
    async with session.begin_nested():
        await session.execute(
            text("DELETE FROM kb_chunks WHERE rel_path = :p"),
            {"p": rel_path},
        )

        for chunk in chunks:
            vec_val = (
                chunk.embedding
                if isinstance(chunk.embedding, str)
                else _vec_str(chunk.embedding)
            )
            await session.execute(
                text(
                    """
                    INSERT INTO kb_chunks
                        (rel_path, doc_id, section, ord, text, chunk_hash,
                         authority_tier, authority_weight, parent_category, niches,
                         tags, kind, source_url, embedding, tsv)
                    VALUES
                        (:rel_path, :doc_id, :section, :ord, :text, :chunk_hash,
                         :authority_tier, :authority_weight, :parent_category, :niches,
                         :tags, :kind, :source_url,
                         CAST(:embedding AS vector),
                         to_tsvector('english', :text))
                    """
                ),
                {
                    "rel_path": rel_path,
                    "doc_id": fm.id,
                    "section": chunk.section,
                    "ord": chunk.ord,
                    "text": chunk.text,
                    "chunk_hash": chunk.chunk_hash,
                    "authority_tier": int(fm.authority_tier),
                    "authority_weight": fm.authority_weight,
                    "parent_category": fm.parent_category,
                    "niches": fm.niches,
                    "tags": fm.tags,
                    "kind": fm.kind,
                    "source_url": fm.source_url,
                    "embedding": vec_val,
                },
            )

        await session.execute(
            text(
                """
                INSERT INTO kb_documents (rel_path, doc_id, file_hash, frontmatter, updated_at)
                VALUES (:rel_path, :doc_id, :file_hash, CAST(:frontmatter AS jsonb), now())
                ON CONFLICT (rel_path) DO UPDATE
                    SET file_hash   = EXCLUDED.file_hash,
                        frontmatter = EXCLUDED.frontmatter,
                        updated_at  = now()
                """
            ),
            {
                "rel_path": rel_path,
                "doc_id": fm.id,
                "file_hash": file_hash,
                "frontmatter": fm.model_dump_json(),
            },
        )

    log.info(
        "knowledge ETL: ingested %s — %d added, %d reused",
        rel_path,
        len(to_embed),
        len(to_reuse),
    )
    return IngestResult(
        rel_path=rel_path,
        chunks_added=len(to_embed),
        chunks_reused=len(to_reuse),
        skipped_file=False,
    )


async def ingest_vault(
    session: AsyncSession,
    client: AsyncOpenAI,
    vault_root: Path,
) -> list[IngestResult]:
    """Full vault scan — ingest all .md files under vault_root.

    Skips .obsidian/, .git/, and non-.md files.
    Errors per-file are logged and returned in results; does NOT abort the run.
    """
    results: list[IngestResult] = []

    md_files = [
        p
        for p in vault_root.rglob("*.md")
        if ".obsidian" not in p.parts and ".git" not in p.parts
    ]

    log.info("knowledge ETL: vault scan found %d markdown files", len(md_files))

    for path in md_files:
        result = await ingest_file(session, client, path, vault_root)
        results.append(result)

    added = sum(r.chunks_added for r in results)
    reused = sum(r.chunks_reused for r in results)
    skipped = sum(1 for r in results if r.skipped_file)
    errors = sum(1 for r in results if r.validation_error)

    log.info(
        "knowledge ETL: vault scan complete — %d files, %d added, %d reused, %d skipped, %d errors",
        len(md_files),
        added,
        reused,
        skipped,
        errors,
    )
    return results
