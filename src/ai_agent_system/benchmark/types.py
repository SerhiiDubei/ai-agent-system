"""Shared types for the benchmark runner."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
from pydantic import BaseModel, Field

# ── OpenRouter pricing (per 1M tokens, USD) ──────────────────────────────────
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_id: (input_$/1M, output_$/1M) — from OpenRouter catalog 2026-04-28
    # ── OpenAI ──
    "openai/gpt-4o-mini":              (0.150,  0.600),
    "openai/gpt-4o":                   (2.500, 10.000),
    "openai/gpt-4-turbo":             (10.000, 30.000),
    "openai/gpt-4.1":                  (2.000,  8.000),
    "openai/gpt-4.1-mini":             (0.400,  1.600),
    "openai/gpt-4.1-nano":             (0.100,  0.400),
    "openai/gpt-5":                    (1.250, 10.000),
    "openai/gpt-5-mini":               (0.250,  2.000),
    "openai/gpt-5-nano":               (0.050,  0.400),
    # ── Anthropic ──
    "anthropic/claude-3-haiku":        (0.250,  1.250),
    "anthropic/claude-3.5-haiku":      (0.800,  4.000),
    "anthropic/claude-haiku-4.5":      (1.000,  5.000),
    "anthropic/claude-3.7-sonnet":     (3.000, 15.000),
    "anthropic/claude-sonnet-4":       (3.000, 15.000),
    "anthropic/claude-sonnet-4.5":     (3.000, 15.000),
    "anthropic/claude-sonnet-4.6":     (3.000, 15.000),
    "anthropic/claude-opus-4":        (15.000, 75.000),
    # ── Google ──
    "google/gemini-2.0-flash-001":     (0.100,  0.400),
    "google/gemini-2.5-flash":         (0.300,  2.500),
    "google/gemini-2.5-pro":           (1.250, 10.000),
    # ── DeepSeek ──
    "deepseek/deepseek-chat":          (0.320,  0.890),
    "deepseek/deepseek-r1":            (0.700,  2.500),
}


# ── Operation output schemas ──────────────────────────────────────────────────

class PageElements(BaseModel):
    """Semantic elements extracted from a landing page."""
    primary_cta: str = Field(description="The main call-to-action button text")
    hero_headline: str = Field(description="The primary headline/hero text on the page")
    lead_form_present: bool = Field(description="Whether a lead capture form exists")
    trust_signals: list[str] = Field(description="Trust signals found (reviews, BBB, guarantees, etc.)")
    key_benefits: list[str] = Field(description="Top 3 benefits communicated to the visitor")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall extraction confidence")


class PainPointList(BaseModel):
    """Pain points identified in landing page copy."""
    pain_points: list[str] = Field(
        description="Concrete pain points WITH situational trigger. "
                    "Format: '<trigger situation> → <pain felt>'. "
                    "NO platitudes like 'peace of mind' or 'better life'."
    )
    target_emotion: str = Field(description="Primary emotion the page is addressing")
    urgency_level: Literal["low", "medium", "high"] = Field(
        description="How urgently the problem is framed"
    )
    audience_age_skew: Literal["under_35", "35_55", "55_plus", "mixed"] = Field(
        description="Inferred target age from copy tone and language"
    )


class ABHypothesis(BaseModel):
    """A single A/B test hypothesis."""
    element: str = Field(description="Specific page element to test (e.g. 'hero headline', 'CTA button text')")
    control: str = Field(description="Current state (what's on the page now)")
    variant: str = Field(description="Proposed change (concrete copy or design change)")
    rationale: str = Field(description="Why this change should improve conversion, grounded in psychology or data")
    primary_metric: str = Field(description="KPI to measure (e.g. 'ZIP submit rate', 'scroll depth', 'CTR')")
    expected_lift: str = Field(description="Expected lift range, e.g. '5–15%' with brief justification")
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Implementation risk: low=copy only, medium=layout, high=flow change"
    )


# ── Benchmark result dataclass ────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: int
    operation: str
    model_id: str
    success: bool
    latency_ms: int
    retries: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    quality_score: float          # 0.0–10.0
    quality_notes: list[str]      # human-readable score breakdown
    output_preview: str           # short string summary of output
    error: str | None = None


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_id, (0.50, 1.50))  # fallback pricing
    return (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000
