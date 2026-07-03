"""Pydantic schemas for Marketing Context — N4.

MarketingContext is the single source of truth that feeds N5-N7 agents.
All downstream agents consume: personas, pain_points, user_flow, channel_profile.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

TrafficSource = Literal[
    "meta", "google_search", "google_display", "tiktok", "snapchat", "youtube",
    "email", "organic",
]

PageGoal = Literal[
    "zip_submit", "phone_call", "lead_form", "quiz_complete", "book_demo", "signup",
]

DigitalLiteracy = Literal["low", "medium", "high"]

IncomeBand = Literal[
    "under_30k", "30_60k", "60_100k", "100_200k", "over_200k", "unknown",
]

PersonaRole = Literal["primary_buyer", "influencer", "decision_helper", "blocker"]

ContextStatus = Literal["draft", "approved", "archived"]


# ── Pain point ────────────────────────────────────────────────────────────────

class PainPoint(BaseModel):
    label: str = Field(..., description="Short label, 3-7 words")
    description: str = Field(
        ..., description="One-sentence concrete pain with observable trigger"
    )
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    frequency: Literal["one_time", "occasional", "frequent", "constant"] = "occasional"
    addressable_by_offer: bool = True

    @model_validator(mode="after")
    def reject_platitudes(self) -> "PainPoint":
        platitudes = ["better life", "save money", "be happy", "more freedom", "improve life"]
        low = self.description.lower()
        if any(p in low for p in platitudes):
            raise ValueError(
                f"Pain description is a platitude: '{self.description}'. "
                "Rewrite with a concrete observable trigger."
            )
        return self


# ── Channel profiles (discriminated union) ────────────────────────────────────

class MetaChannelProfile(BaseModel):
    channel: Literal["meta"] = "meta"
    primary_placement: Literal["feed", "stories", "reels", "marketplace"]
    typical_mindset: str = Field(
        ..., description="Push-interrupt context: what were they doing before the ad?"
    )
    creative_format_pref: list[Literal[
        "static_image", "carousel", "video_15s", "video_30s", "ugc_style"
    ]]
    age_targeting_note: str | None = Field(
        None,
        description="Special Ad Categories that restrict age/zip (housing, credit, employment)",
    )


class GoogleSearchChannelProfile(BaseModel):
    channel: Literal["google_search"] = "google_search"
    intent_level: Literal["informational", "commercial", "transactional"]
    typical_query_examples: list[str] = Field(..., min_length=2, max_length=8)
    competitor_density: Literal["low", "medium", "high", "saturated"]


class GoogleDisplayChannelProfile(BaseModel):
    channel: Literal["google_display"] = "google_display"
    typical_mindset: str
    audience_signal: str = Field(..., description="e.g. 'in-market: home improvement'")


class TikTokChannelProfile(BaseModel):
    channel: Literal["tiktok"] = "tiktok"
    typical_mindset: str
    age_skew: Literal["under_25", "25_34", "mixed"]
    hook_window_seconds: int = Field(3, ge=1, le=10)


class SnapchatChannelProfile(BaseModel):
    channel: Literal["snapchat"] = "snapchat"
    age_skew: Literal["under_25", "25_34"]
    typical_mindset: str


class YouTubeChannelProfile(BaseModel):
    channel: Literal["youtube"] = "youtube"
    ad_format: Literal["pre_roll", "mid_roll", "bumper", "discovery"]
    skip_after_seconds: int = Field(5, ge=0)


class EmailChannelProfile(BaseModel):
    channel: Literal["email"] = "email"
    list_type: Literal["owned", "co_reg", "third_party"]
    typical_mindset: str


class OrganicChannelProfile(BaseModel):
    channel: Literal["organic"] = "organic"
    traffic_intent: Literal["informational", "commercial", "navigational"]


ChannelProfile = Annotated[
    Union[
        MetaChannelProfile,
        GoogleSearchChannelProfile,
        GoogleDisplayChannelProfile,
        TikTokChannelProfile,
        SnapchatChannelProfile,
        YouTubeChannelProfile,
        EmailChannelProfile,
        OrganicChannelProfile,
    ],
    Field(discriminator="channel"),
]


# ── Persona ───────────────────────────────────────────────────────────────────

class Persona(BaseModel):
    name: str = Field(
        ...,
        description=(
            "Memorable niche-specific label. e.g. 'Florida Helen, 72, fall-risk widow'. "
            "NOT generic like 'John, 35, marketing manager'."
        ),
    )
    role: PersonaRole
    age_range: str = Field(..., pattern=r"^\d{2}-\d{2,3}$|^\d{2}\+$")
    location_context: str = Field(
        ..., description="Geo + life stage, e.g. 'Florida retiree, owns home outright'"
    )
    income_band: IncomeBand
    digital_literacy: DigitalLiteracy

    primary_job: str = Field(
        ...,
        description="JTBD: 'When ___, I want to ___, so I can ___'",
    )
    pain_points: list[PainPoint] = Field(..., min_length=2, max_length=6)
    trust_needs: list[str] = Field(
        ..., min_length=2, max_length=5,
        description="What must the page demonstrate before they convert?",
    )
    decision_triggers: list[str] = Field(
        ..., min_length=2, max_length=5,
        description="What pushes them from research to action?",
    )
    objections: list[str] = Field(
        ..., min_length=1, max_length=5,
        description="Specific objections likely to kill conversion",
    )
    channel_behavior: str = Field(
        ...,
        description="Device, scroll speed, time-of-day, return-visit pattern",
    )

    @model_validator(mode="after")
    def reject_generic_name(self) -> "Persona":
        generic_combo = ["john", "jane", "alex", "sam", "chris"]
        first = self.name.split(",")[0].strip().lower()
        if first in generic_combo and "manager" in self.name.lower():
            raise ValueError(
                f"Persona name '{self.name}' is the canonical generic-persona anti-pattern."
            )
        return self


# ── User flow ─────────────────────────────────────────────────────────────────

class UserFlowStage(BaseModel):
    stage: Literal[
        "awareness", "consideration", "evaluation", "intent", "action", "post_action"
    ]
    description: str
    typical_duration: str = Field(..., description="e.g. '5 sec', '2 days'")
    user_question: str = Field(..., description="The question in their head at this stage")
    page_must_answer: str


class UserFlow(BaseModel):
    stages: list[UserFlowStage] = Field(..., min_length=3, max_length=7)
    primary_friction_point: str
    drop_off_hypothesis: str = Field(..., description="Where most users drop off and why")


# ── Audience profile ──────────────────────────────────────────────────────────

class AudienceProfile(BaseModel):
    primary_persona_name: str = Field(..., description="Must match one Persona.name exactly")
    secondary_persona_names: list[str] = Field(default_factory=list)
    estimated_primary_share: float = Field(..., ge=0.0, le=1.0)
    market: str = Field(..., description="ISO country/region, e.g. 'US-FL'")
    language: str = Field(..., pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    total_addressable_population_note: str | None = None


# ── Top-level container ───────────────────────────────────────────────────────

class MarketingContext(BaseModel):
    schema_version: int = 1
    niche: str
    parent_category: str
    market: str
    language: str = Field(..., pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    traffic_source_primary: TrafficSource
    page_goal: PageGoal
    primary_metric: str
    guardrail_metrics: list[str] = Field(default_factory=list)
    business_constraints: str | None = None

    personas: list[Persona] = Field(..., min_length=3, max_length=5)
    pain_points_aggregate: list[PainPoint] = Field(..., min_length=3)
    user_flow: UserFlow
    audience_profile: AudienceProfile
    channel_profile: ChannelProfile

    source_brief: str
    grounding_chunks_used: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def primary_persona_exists(self) -> "MarketingContext":
        names = {p.name for p in self.personas}
        if self.audience_profile.primary_persona_name not in names:
            raise ValueError(
                f"audience_profile.primary_persona_name "
                f"'{self.audience_profile.primary_persona_name}' "
                f"not found in personas: {sorted(names)}"
            )
        return self

    @model_validator(mode="after")
    def channel_matches_traffic_source(self) -> "MarketingContext":
        if self.channel_profile.channel != self.traffic_source_primary:
            raise ValueError(
                f"channel_profile.channel '{self.channel_profile.channel}' "
                f"does not match traffic_source_primary '{self.traffic_source_primary}'"
            )
        return self


# ── Judge verdict ─────────────────────────────────────────────────────────────

class SanityVerdict(BaseModel):
    passed: bool = Field(..., description="True if no critical issues found")
    issues: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
