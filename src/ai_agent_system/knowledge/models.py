"""Pydantic frontmatter schema for Obsidian notes — N3.

Every note in the vault MUST have valid frontmatter matching NoteFrontmatter.
ETL rejects files that fail validation (logs error, skips without crashing).

Authority tier hierarchy (per N3 research):
  Tier 1 — Real A/B test outcomes from our own experiments (weight 1.0)
  Tier 2 — Hand-curated notes by the team                  (weight 0.7)
  Tier 3 — GoodUI / Growth.Design imports                  (weight 0.4)
"""

from __future__ import annotations

from datetime import date
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AuthorityTier(IntEnum):
    REAL_TEST = 1     # our own A/B test results — highest weight
    USER_CURATED = 2  # hand-written team notes
    EXTERNAL = 3      # GoodUI, Growth.Design, other imports


TIER_WEIGHTS: dict[int, float] = {
    AuthorityTier.REAL_TEST: 1.0,
    AuthorityTier.USER_CURATED: 0.7,
    AuthorityTier.EXTERNAL: 0.4,
}


class NoteFrontmatter(BaseModel):
    """Canonical schema for Obsidian note frontmatter.

    All fields required unless noted. ETL rejects any note missing required fields.
    """

    id: str = Field(..., pattern=r"^[a-z0-9_-]{6,}$")
    title: str = Field(..., min_length=3, max_length=200)

    kind: Literal["pattern", "test", "principle", "case_study", "research_note"]
    parent_category: Literal["home_improvement", "dating"]
    niches: list[str] = Field(default_factory=list, max_length=10)
    tags: list[str] = Field(default_factory=list)

    authority_tier: AuthorityTier

    source_url: str | None = None
    source_name: str | None = None

    # Author-stated confidence [0.0, 1.0] — NOT the same as retrieval score.
    # Per N3: treat as prior; isotonic regression calibration deferred to v2.
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    created: date
    updated: date

    # Optional: actual measured impact, e.g. {"cvr_lift": 0.12}
    metric_impact: dict[str, float] | None = None

    @field_validator("niches")
    @classmethod
    def _slugged_niches(cls, v: list[str]) -> list[str]:
        for n in v:
            if not n.replace("_", "").isalnum():
                raise ValueError(f"niche must be alphanumeric slug, got: {n!r}")
        return v

    @property
    def authority_weight(self) -> float:
        return TIER_WEIGHTS[int(self.authority_tier)]
