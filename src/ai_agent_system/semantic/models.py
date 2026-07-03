"""Pydantic domain models for N2 semantic role mapping.

The LLM receives a list of DomMark objects (extracted from HTML) plus a
screenshot, and returns a PageSemanticMap with one RoleAssignment per mark.
Taxonomy invariants (single primary_cta, single hero_image) are enforced
via model_validators — NOT via prompt alone.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

# ── Taxonomy ──────────────────────────────────────────────────────────────────
SemanticRoleType = Literal[
    "primary_cta",
    "secondary_cta",
    "hero_image",
    "hero_headline",
    "hero_subheadline",
    "lead_form",
    "phone_block",
    "trust_block",
    "social_proof_block",
    "testimonial_block",
    "before_after",
    "pricing_block",
    "service_list",
    "faq_block",
    "guarantee_block",
    "credentials_block",
    "footer_block",
    "navigation",
    "unknown",
]

PageArchetypeType = Literal[
    "lead_capture",
    "service_explainer",
    "pricing_focused",
    "trust_first",
    "video_first",
    "long_form_sales",
    "other",
]


# ── DOM extraction output ─────────────────────────────────────────────────────
class BoundingBox(BaseModel):
    """Pixel coordinates in the rendered viewport."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DomMark(BaseModel):
    """One candidate DOM element sent to the LLM as part of the marks list."""

    mark_id: int
    tag: str
    text: str = ""
    role_attr: str = ""
    href: str = ""
    class_hint: str = ""
    bbox: Optional[BoundingBox] = None  # populated if JS position data is available


# ── LLM output ───────────────────────────────────────────────────────────────
class RoleAssignment(BaseModel):
    """Semantic role assigned to one DOM element."""

    mark_id: int = Field(description="References DomMark.mark_id from the input list.")
    role: SemanticRoleType
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Only set for image-like roles when the model refines the visual crop.",
    )
    rationale: str = Field(
        max_length=240,
        description="One sentence explaining why this element earned this role.",
    )


class PageSemanticMap(BaseModel):
    """Full semantic classification for one rendered viewport."""

    viewport: Literal["desktop", "mobile"]
    page_archetype: PageArchetypeType
    archetype_confidence: float = Field(ge=0.0, le=1.0)
    assignments: list[RoleAssignment]
    notes: str = Field(
        default="",
        max_length=600,
        description="Anything notable that does not fit a role (animations, exit-intent popups, etc.)",
    )

    @model_validator(mode="after")
    def exactly_one_primary_cta(self) -> "PageSemanticMap":
        """Demote duplicate primary_cta assignments to secondary_cta by confidence."""
        primaries = [a for a in self.assignments if a.role == "primary_cta"]
        if len(primaries) > 1:
            primaries.sort(key=lambda a: a.confidence, reverse=True)
            for demoted in primaries[1:]:
                demoted.role = "secondary_cta"
        return self

    @model_validator(mode="after")
    def at_most_one_hero_image(self) -> "PageSemanticMap":
        """Demote duplicate hero_image assignments to unknown by confidence."""
        heroes = [a for a in self.assignments if a.role == "hero_image"]
        if len(heroes) > 1:
            heroes.sort(key=lambda a: a.confidence, reverse=True)
            for demoted in heroes[1:]:
                demoted.role = "unknown"
        return self

    def role_map(self) -> dict[SemanticRoleType, list[RoleAssignment]]:
        """Group assignments by role for downstream consumers."""
        result: dict[str, list[RoleAssignment]] = {}
        for a in self.assignments:
            result.setdefault(a.role, []).append(a)
        return result  # type: ignore[return-value]
