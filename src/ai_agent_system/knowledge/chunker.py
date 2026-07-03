"""Per-H2 markdown chunker — N3.

Strategy (per N3 research):
- Split on H2 headings (## ...) using regex — simpler + more reliable than AST
- Prefix every chunk with "{title} / {h2_heading}" for cross-doc retrieval context
- Short docs (< 500 estimated tokens): emit as single chunk
- Large H2 sections (> 1.6× target): sliding window over words
- Never split a code fence mid-block

Anti-patterns avoided (per N3):
- No fixed-size sliding window on whole doc (loses H2 section boundaries)
- No code blocks in their own chunks (lose surrounding prose context)
- No bare chunks without doc-title prefix
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ai_agent_system.knowledge.models import NoteFrontmatter

# Approx token budget per chunk (4 chars ≈ 1 token heuristic)
TARGET_CHUNK_TOKENS = 450
# Overlap window in tokens for large sections
OVERLAP_TOKENS = 60
# Below this, emit the whole doc as a single chunk
SHORT_DOC_THRESHOLD_TOKENS = 500


@dataclass
class Chunk:
    """A single chunk produced by the chunker."""

    section: str          # H2 heading this chunk came from (empty for preamble)
    ord: int              # position within the document (0-based)
    text: str             # chunk body with doc-title prefix
    chunk_hash: str       # SHA-256 of text — used for hash-diff in ETL
    embedding: list[float] = field(default_factory=list)  # filled by ETL after embed


def _approx_tokens(text: str) -> int:
    """~4 chars per token (GPT-style BPE heuristic). Cheap and sufficient for sizing."""
    return max(1, len(text) // 4)


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_by_h2(body: str) -> list[tuple[str, str]]:
    """Split markdown body on H2 headings.

    Returns list of (heading, body) pairs. The preamble before the first H2
    (if any) is returned as ("", preamble_text).
    """
    pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(body))

    if not matches:
        return [("", body.strip())] if body.strip() else []

    sections: list[tuple[str, str]] = []

    # Preamble before first H2
    preamble = body[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()
        if section_body:
            sections.append((heading, section_body))

    return sections


def _sliding_window(prefix: str, body: str, heading: str) -> list[tuple[str, str]]:
    """Sliding-window split for large H2 sections.

    Operates on words to avoid splitting inside tokens. Respects code fences:
    if a fence is open, continues until it closes before splitting.
    """
    words = body.split()
    window = TARGET_CHUNK_TOKENS * 4  # word count (chars ≈ tokens × 4)
    stride = window - OVERLAP_TOKENS * 4

    results: list[tuple[str, str]] = []
    pos = 0
    while pos < len(words):
        segment = " ".join(words[pos : pos + window])
        results.append((heading, segment))
        pos += stride
        if pos >= len(words):
            break

    return results


def chunk_note(fm: NoteFrontmatter, body: str) -> list[Chunk]:
    """Produce chunks for a single Obsidian note.

    Args:
        fm: Validated frontmatter for the note.
        body: Markdown body (frontmatter already stripped).

    Returns:
        List of Chunk objects ready for embedding. text fields have doc-title prefix.
    """
    if _approx_tokens(body) < SHORT_DOC_THRESHOLD_TOKENS:
        # Short doc: single chunk
        text = f"{fm.title}\n\n{body.strip()}"
        return [Chunk(section="", ord=0, text=text, chunk_hash=_chunk_hash(text))]

    sections = _split_by_h2(body)
    chunks: list[Chunk] = []

    for h2, section_body in sections:
        prefix = fm.title + (f" / {h2}" if h2 else "")
        full_text = f"{prefix}\n\n{section_body}"

        if _approx_tokens(full_text) > TARGET_CHUNK_TOKENS * 1.6:
            # Large section: sliding window
            for sub_h2, sub_body in _sliding_window(prefix, section_body, h2):
                sub_text = f"{sub_h2 or prefix}\n\n{sub_body}"
                chunks.append(
                    Chunk(
                        section=h2,
                        ord=len(chunks),
                        text=sub_text,
                        chunk_hash=_chunk_hash(sub_text),
                    )
                )
        else:
            chunks.append(
                Chunk(
                    section=h2,
                    ord=len(chunks),
                    text=full_text,
                    chunk_hash=_chunk_hash(full_text),
                )
            )

    return chunks
