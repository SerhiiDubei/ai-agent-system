"""Quality scoring heuristics for each benchmark operation.

All scorers return (score: float 0-10, notes: list[str]).
Scoring is intentionally heuristic — no LLM judge to keep benchmark cost low.
"""
from __future__ import annotations

from ai_agent_system.benchmark.types import PageElements, PainPointList, ABHypothesis
from ai_agent_system.marketing.models import MarketingContext

_PLATITUDES = {
    "peace of mind", "better life", "save money", "convenient", "easy to use",
    "worry-free", "stress-free", "hassle-free", "life-changing", "game-changer",
    "affordable", "high quality", "best in class", "top rated",
}


# ── Drafter scorer ────────────────────────────────────────────────────────────

def score_drafter(ctx: MarketingContext) -> tuple[float, list[str]]:
    """Score a MarketingContext on 5 dimensions, 2pts each = 10 max."""
    score = 0.0
    notes: list[str] = []

    # 1. Persona count (3-5 required)
    n = len(ctx.personas)
    if 3 <= n <= 5:
        score += 2
        notes.append(f"✓ persona_count={n} (valid range 3-5)")
    else:
        notes.append(f"✗ persona_count={n} (need 3-5)")

    # 2. Decision-helper persona for senior niches
    roles = [p.role for p in ctx.personas]
    has_helper = "decision_helper" in roles
    if has_helper:
        score += 2
        notes.append("✓ decision_helper persona present")
    else:
        notes.append("✗ missing decision_helper (required for 55+ niches)")

    # 3. JTBD format on primary_job
    jtbd_ok = 0
    for p in ctx.personas:
        j = p.primary_job.lower()
        if "when" in j and "want" in j and "so" in j:
            jtbd_ok += 1
    ratio = jtbd_ok / max(len(ctx.personas), 1)
    pts = round(ratio * 2, 1)
    score += pts
    notes.append(f"{'✓' if pts == 2 else '~'} JTBD format: {jtbd_ok}/{len(ctx.personas)} personas")

    # 4. No platitudes in pain points
    all_pain_text = " ".join(
        " ".join(pp.description for pp in p.pain_points)
        for p in ctx.personas
    ).lower()
    found_platitudes = [p for p in _PLATITUDES if p in all_pain_text]
    if not found_platitudes:
        score += 2
        notes.append("✓ no platitudes in pain points")
    else:
        notes.append(f"✗ platitudes found: {found_platitudes[:3]}")

    # 5. Realistic income bands (not everyone on 60_100k)
    bands = [p.income_band for p in ctx.personas]
    high_band_only = all(b in ("60_100k", "100k_plus") for b in bands)
    if not high_band_only:
        score += 2
        notes.append(f"✓ realistic income mix: {set(bands)}")
    else:
        notes.append(f"✗ all personas assigned high income bands: {bands}")

    return round(score, 1), notes


# ── Semantic extractor scorer ─────────────────────────────────────────────────

def score_semantic(result: PageElements) -> tuple[float, list[str]]:
    """Score PageElements extraction. 10pts max."""
    score = 0.0
    notes: list[str] = []

    # 1. Primary CTA is specific (not empty, not generic)
    generic_cta = {"click here", "learn more", "submit", "go", "ok"}
    if result.primary_cta and result.primary_cta.lower() not in generic_cta:
        score += 3
        notes.append(f"✓ primary_cta='{result.primary_cta}'")
    else:
        notes.append(f"✗ primary_cta missing or too generic: '{result.primary_cta}'")

    # 2. Hero headline extracted
    if result.hero_headline and len(result.hero_headline) > 10:
        score += 2
        notes.append(f"✓ hero_headline='{result.hero_headline[:60]}...'")
    else:
        notes.append(f"✗ hero_headline missing or too short")

    # 3. Trust signals (2+ items)
    ts = len(result.trust_signals)
    if ts >= 2:
        score += 2
        notes.append(f"✓ {ts} trust signals found")
    elif ts == 1:
        score += 1
        notes.append(f"~ only 1 trust signal found")
    else:
        notes.append("✗ no trust signals found")

    # 4. Confidence >= 0.7
    if result.confidence >= 0.7:
        score += 2
        notes.append(f"✓ confidence={result.confidence:.2f}")
    elif result.confidence >= 0.5:
        score += 1
        notes.append(f"~ confidence={result.confidence:.2f} (below 0.7)")
    else:
        notes.append(f"✗ confidence={result.confidence:.2f} (too low)")

    # 5. Key benefits (2+)
    if len(result.key_benefits) >= 2:
        score += 1
        notes.append(f"✓ {len(result.key_benefits)} key benefits identified")
    else:
        notes.append(f"✗ only {len(result.key_benefits)} key benefits")

    return round(score, 1), notes


# ── Pain point miner scorer ───────────────────────────────────────────────────

def score_pain_points(result: PainPointList) -> tuple[float, list[str]]:
    """Score PainPointList extraction. 10pts max."""
    score = 0.0
    notes: list[str] = []

    # 1. Volume: 3+ pain points
    n = len(result.pain_points)
    if n >= 4:
        score += 3
        notes.append(f"✓ {n} pain points (excellent)")
    elif n == 3:
        score += 2
        notes.append(f"✓ {n} pain points (sufficient)")
    elif n >= 1:
        score += 1
        notes.append(f"~ only {n} pain points (need 3+)")
    else:
        notes.append("✗ no pain points extracted")

    # 2. No platitudes in pain point text
    combined = " ".join(result.pain_points).lower()
    found = [p for p in _PLATITUDES if p in combined]
    if not found:
        score += 3
        notes.append("✓ no platitudes in pain points")
    else:
        notes.append(f"✗ platitudes: {found[:3]}")

    # 3. Has trigger pattern (→ or "when" or "after")
    trigger_words = ["→", "when ", "after ", "because ", "since ", "worried"]
    has_triggers = sum(
        1 for pp in result.pain_points
        if any(t in pp.lower() for t in trigger_words)
    )
    ratio = has_triggers / max(n, 1)
    pts = round(ratio * 2, 1)
    score += pts
    notes.append(
        f"{'✓' if pts >= 1.5 else '~'} trigger phrases: {has_triggers}/{n} pain points"
    )

    # 4. Appropriate urgency for safety niche
    if result.urgency_level == "high":
        score += 2
        notes.append(f"✓ urgency_level=high (correct for safety niche)")
    elif result.urgency_level == "medium":
        score += 1
        notes.append(f"~ urgency_level=medium (expected high for shower/tub safety)")
    else:
        notes.append(f"✗ urgency_level={result.urgency_level} (too low for safety niche)")

    return round(score, 1), notes


# ── Hypothesis scorer — YOUR CONTRIBUTION ────────────────────────────────────

def score_hypothesis(result: ABHypothesis) -> tuple[float, list[str]]:
    """Score an A/B hypothesis. 10pts max.

    TODO: This scoring logic is where YOUR domain knowledge matters most.
    A good hypothesis should earn points for the properties you care about.

    Currently: basic structural checks only (4pts max).
    Add your own criteria below to reach 10pts.

    Suggested areas to score (pick what matters to you):
    - Is the element specific enough? ("hero headline" > "page copy")
    - Does the variant describe a CONCRETE change, not just "make it better"?
    - Is the rationale grounded in psychology/data, not vague?
    - Is the expected_lift range realistic (5-30% for copy tests)?
    - Does the primary_metric match the page_goal (ZIP submit → submit rate)?
    - Is risk_level correctly assigned?

    Edit this function to add your criteria.
    """
    score = 0.0
    notes: list[str] = []

    # ── Structural checks (built-in, 4pts) ────────────────────────────────────

    # 1. Element is specific
    vague_elements = {"page", "content", "copy", "design", "layout", "button"}
    if result.element and result.element.lower() not in vague_elements:
        score += 1
        notes.append(f"✓ element='{result.element}'")
    else:
        notes.append(f"✗ element too vague: '{result.element}'")

    # 2. Variant is not a rewording of control
    if result.variant and result.variant.lower() != result.control.lower():
        score += 1
        notes.append(f"✓ variant differs from control")
    else:
        notes.append(f"✗ variant is same as control")

    # 3. Has a primary metric
    if result.primary_metric:
        score += 1
        notes.append(f"✓ primary_metric='{result.primary_metric}'")
    else:
        notes.append("✗ no primary_metric")

    # 4. Risk level assigned
    if result.risk_level:
        score += 1
        notes.append(f"✓ risk_level='{result.risk_level}'")

    # ── YOUR SCORING CRITERIA (add up to 6 more points) ──────────────────────
    # Example structure — replace with your own logic:
    #
    # if <your condition>:
    #     score += <pts>
    #     notes.append("✓ <reason>")
    # else:
    #     notes.append("✗ <reason>")
    #
    # Hint: the rationale, expected_lift, and control/variant quality
    # are the most important dimensions for real A/B testing value.

    notes.append("ℹ️  hypothesis scorer: add your criteria for 6 more points")

    return round(score, 1), notes
