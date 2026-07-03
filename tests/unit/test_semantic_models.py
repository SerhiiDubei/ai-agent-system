"""Unit tests for N2 PageSemanticMap model validators.

Verifies that taxonomy invariants enforced by model_validators work correctly:
- exactly_one_primary_cta: duplicates demoted to secondary_cta by confidence
- at_most_one_hero_image: duplicates demoted to unknown by confidence
"""

import pytest
from pydantic import ValidationError

from ai_agent_system.semantic.models import BoundingBox, DomMark, PageSemanticMap, RoleAssignment


def _assignment(mark_id: int, role: str, confidence: float = 0.9) -> dict:
    return {
        "mark_id": mark_id,
        "role": role,
        "confidence": confidence,
        "rationale": "test rationale",
    }


def _map(**kwargs) -> PageSemanticMap:
    defaults = {
        "viewport": "desktop",
        "page_archetype": "lead_capture",
        "archetype_confidence": 0.85,
        "assignments": [],
        "notes": "",
    }
    defaults.update(kwargs)
    return PageSemanticMap(**defaults)


# ── Primary CTA deduplication ─────────────────────────────────────────────────

def test_single_primary_cta_unchanged():
    m = _map(assignments=[_assignment(1, "primary_cta", 0.95)])
    primaries = [a for a in m.assignments if a.role == "primary_cta"]
    assert len(primaries) == 1


def test_duplicate_primary_cta_demoted():
    m = _map(assignments=[
        _assignment(1, "primary_cta", confidence=0.9),
        _assignment(2, "primary_cta", confidence=0.7),
    ])
    primaries = [a for a in m.assignments if a.role == "primary_cta"]
    secondaries = [a for a in m.assignments if a.role == "secondary_cta"]
    assert len(primaries) == 1
    assert len(secondaries) == 1
    # Higher confidence kept as primary
    assert primaries[0].mark_id == 1
    assert secondaries[0].mark_id == 2


def test_three_primary_ctas_demoted():
    m = _map(assignments=[
        _assignment(1, "primary_cta", confidence=0.8),
        _assignment(2, "primary_cta", confidence=0.95),
        _assignment(3, "primary_cta", confidence=0.6),
    ])
    primaries = [a for a in m.assignments if a.role == "primary_cta"]
    secondaries = [a for a in m.assignments if a.role == "secondary_cta"]
    assert len(primaries) == 1
    assert primaries[0].mark_id == 2  # highest confidence
    assert len(secondaries) == 2


# ── Hero image deduplication ──────────────────────────────────────────────────

def test_single_hero_image_unchanged():
    m = _map(assignments=[_assignment(1, "hero_image", 0.9)])
    heroes = [a for a in m.assignments if a.role == "hero_image"]
    assert len(heroes) == 1


def test_duplicate_hero_image_demoted_to_unknown():
    m = _map(assignments=[
        _assignment(1, "hero_image", confidence=0.85),
        _assignment(2, "hero_image", confidence=0.65),
    ])
    heroes = [a for a in m.assignments if a.role == "hero_image"]
    unknowns = [a for a in m.assignments if a.role == "unknown"]
    assert len(heroes) == 1
    assert heroes[0].mark_id == 1
    assert len(unknowns) == 1
    assert unknowns[0].mark_id == 2


# ── role_map helper ───────────────────────────────────────────────────────────

def test_role_map_groups_correctly():
    m = _map(assignments=[
        _assignment(1, "primary_cta"),
        _assignment(2, "trust_block"),
        _assignment(3, "trust_block"),
        _assignment(4, "hero_headline"),
    ])
    rmap = m.role_map()
    assert len(rmap["primary_cta"]) == 1
    assert len(rmap["trust_block"]) == 2
    assert len(rmap["hero_headline"]) == 1


# ── Confidence validation ─────────────────────────────────────────────────────

def test_confidence_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        RoleAssignment(mark_id=1, role="primary_cta", confidence=1.5, rationale="x")

    with pytest.raises(ValidationError):
        RoleAssignment(mark_id=1, role="primary_cta", confidence=-0.1, rationale="x")


# ── BoundingBox validation ────────────────────────────────────────────────────

def test_bounding_box_valid():
    bb = BoundingBox(x=0, y=100, width=300, height=50)
    assert bb.x == 0


def test_bounding_box_width_must_be_positive():
    with pytest.raises(ValidationError):
        BoundingBox(x=0, y=0, width=0, height=50)


# ── Invalid role rejected ─────────────────────────────────────────────────────

def test_invalid_role_rejected():
    with pytest.raises(ValidationError):
        RoleAssignment(mark_id=1, role="not_a_real_role", confidence=0.8, rationale="x")
