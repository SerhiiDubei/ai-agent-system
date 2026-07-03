"""Unit tests for the knowledge chunker — N3."""

from __future__ import annotations

from datetime import date

import pytest

from ai_agent_system.knowledge.chunker import (
    SHORT_DOC_THRESHOLD_TOKENS,
    TARGET_CHUNK_TOKENS,
    Chunk,
    _approx_tokens,
    _chunk_hash,
    _split_by_h2,
    chunk_note,
)
from ai_agent_system.knowledge.models import AuthorityTier, NoteFrontmatter


def _fm(**kwargs) -> NoteFrontmatter:
    defaults = {
        "id": "test-note",
        "title": "Test Pattern",
        "kind": "pattern",
        "parent_category": "home_improvement",
        "niches": ["walk_in_tub"],
        "authority_tier": AuthorityTier.USER_CURATED,
        "created": date(2026, 1, 1),
        "updated": date(2026, 4, 1),
    }
    defaults.update(kwargs)
    return NoteFrontmatter(**defaults)


# ── _split_by_h2 ──────────────────────────────────────────────────────

def test_split_by_h2_no_headings():
    body = "Some text without headings."
    sections = _split_by_h2(body)
    assert len(sections) == 1
    assert sections[0] == ("", "Some text without headings.")


def test_split_by_h2_single_heading():
    body = "Preamble text.\n\n## Section One\n\nContent here."
    sections = _split_by_h2(body)
    assert len(sections) == 2
    assert sections[0] == ("", "Preamble text.")
    assert sections[1][0] == "Section One"
    assert "Content here" in sections[1][1]


def test_split_by_h2_multiple_headings():
    body = "## First\n\nContent A.\n\n## Second\n\nContent B.\n\n## Third\n\nContent C."
    sections = _split_by_h2(body)
    assert len(sections) == 3
    assert [h for h, _ in sections] == ["First", "Second", "Third"]


def test_split_by_h2_empty_section_skipped():
    # A heading with no body should be skipped
    body = "## Empty\n\n## Has Content\n\nSome text."
    sections = _split_by_h2(body)
    assert len(sections) == 1
    assert sections[0][0] == "Has Content"


def test_split_by_h2_no_preamble_if_starts_with_h2():
    body = "## First Section\n\nContent."
    sections = _split_by_h2(body)
    assert len(sections) == 1
    assert sections[0][0] == "First Section"


# ── chunk_note ────────────────────────────────────────────────────────

def test_chunk_note_short_doc_single_chunk():
    """Docs below SHORT_DOC_THRESHOLD_TOKENS → single chunk."""
    fm = _fm(title="Short Pattern")
    body = "A short note body."  # definitely < 500 tokens
    chunks = chunk_note(fm, body)
    assert len(chunks) == 1
    assert chunks[0].section == ""
    assert chunks[0].ord == 0
    assert "Short Pattern" in chunks[0].text
    assert "short note body" in chunks[0].text


def test_chunk_note_prefix_contains_title():
    """Every chunk must contain the doc title as prefix."""
    fm = _fm(title="Walk-in Tub Trust Block")
    body = "## Overview\n\nTrust signals.\n\n## Examples\n\nSome examples here."
    chunks = chunk_note(fm, body)
    for c in chunks:
        assert "Walk-in Tub Trust Block" in c.text


def test_chunk_note_multi_h2_ord_sequential():
    """ord values are 0, 1, 2, ... across all chunks."""
    fm = _fm(title="Multi Section")
    body = "## A\n\nText A.\n\n## B\n\nText B.\n\n## C\n\nText C."
    chunks = chunk_note(fm, body)
    assert [c.ord for c in chunks] == list(range(len(chunks)))


def test_chunk_note_hash_stable():
    """Same text → same chunk_hash (deterministic)."""
    fm = _fm(title="Stable Hash")
    body = "## Section\n\nSome content that doesn't change."
    chunks1 = chunk_note(fm, body)
    chunks2 = chunk_note(fm, body)
    assert [c.chunk_hash for c in chunks1] == [c.chunk_hash for c in chunks2]


def test_chunk_note_different_content_different_hash():
    """Different text → different chunk_hash."""
    fm = _fm(title="Hash Diff")
    body1 = "## Section\n\nVersion one."
    body2 = "## Section\n\nVersion two."
    c1 = chunk_note(fm, body1)
    c2 = chunk_note(fm, body2)
    assert c1[0].chunk_hash != c2[0].chunk_hash


def test_chunk_note_h2_prefix_with_section_name():
    """Non-preamble chunks include 'Title / Section' prefix."""
    fm = _fm(title="Doc Title")
    body = "## My Section\n\nContent of section."
    chunks = chunk_note(fm, body)
    assert any("Doc Title / My Section" in c.text for c in chunks)


def test_chunk_note_empty_body_returns_empty():
    """Empty body produces no chunks (or one empty chunk — either is fine)."""
    fm = _fm()
    chunks = chunk_note(fm, "")
    # Should not crash; may return empty list or single trivial chunk
    assert isinstance(chunks, list)


# ── _approx_tokens ────────────────────────────────────────────────────

def test_approx_tokens_heuristic():
    """4 chars ≈ 1 token; 400 chars ≈ 100 tokens."""
    assert _approx_tokens("a" * 400) == 100
    assert _approx_tokens("") == 1  # minimum 1


# ── chunk hash ────────────────────────────────────────────────────────

def test_chunk_hash_is_64_chars():
    h = _chunk_hash("hello world")
    assert len(h) == 64  # SHA-256 hex


def test_chunk_hash_deterministic():
    assert _chunk_hash("test") == _chunk_hash("test")
