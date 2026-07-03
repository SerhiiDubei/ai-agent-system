"""Minimum Detectable Effect (MDE) calculator.

For binary conversion-rate A/B tests at standard parameters (alpha=0.05, power=0.80):

    n_per_arm ≈ 16 × p₀(1−p₀) / (p₀ × r)²

where p₀ = baseline rate (decimal, e.g. 0.05 for 5%), r = relative lift (e.g. 0.10 for 10%).

This is the rule-of-thumb formula used by CRO consultants. For high-precision power
analysis use scipy.stats — but for "is this test feasible" decisions, this is enough.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass
class FeasibilityVerdict:
    """Output of mde_feasibility check."""
    feasible: bool
    needed_per_arm: int
    available_per_arm: int
    detectable_relative_lift_pct: float
    reason: str


def sample_size_per_arm(
    *,
    baseline_rate_pct: float,
    relative_lift_pct: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Sample size per arm to detect relative lift at given power.

    Args:
        baseline_rate_pct: e.g. 5.0 means 5%
        relative_lift_pct: e.g. 10.0 means +10% relative (5% → 5.5%)

    Returns:
        Recommended sample size per arm (rounded up).
    """
    if baseline_rate_pct <= 0 or baseline_rate_pct >= 100:
        raise ValueError(f"baseline_rate_pct must be (0, 100), got {baseline_rate_pct}")
    if relative_lift_pct <= 0:
        raise ValueError(f"relative_lift_pct must be > 0, got {relative_lift_pct}")

    p0 = baseline_rate_pct / 100.0
    r = relative_lift_pct / 100.0

    # Rule-of-thumb formula at alpha=0.05, power=0.80
    # n = 16 × p₀(1−p₀) / (p₀ × r)²
    # The "16" coefficient assumes those parameters; lower power → smaller coeff
    coeff = 16.0
    if alpha == 0.05 and power == 0.90:
        coeff = 21.0
    elif alpha == 0.01 and power == 0.80:
        coeff = 22.0

    delta = p0 * r
    n = coeff * p0 * (1 - p0) / (delta ** 2)
    return int(ceil(n))


def detectable_lift(
    *,
    baseline_rate_pct: float,
    available_per_arm: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """What's the smallest RELATIVE LIFT we can detect with this many visitors per arm?

    Solves the formula above for r given n.
    """
    if available_per_arm <= 0:
        return float("inf")
    p0 = baseline_rate_pct / 100.0
    coeff = 16.0
    if alpha == 0.05 and power == 0.90:
        coeff = 21.0
    elif alpha == 0.01 and power == 0.80:
        coeff = 22.0
    # n = coeff × p₀(1−p₀) / (p₀ × r)²
    # → r² = coeff × p₀(1−p₀) / (n × p₀²)
    # → r = sqrt(coeff × (1−p₀) / (n × p₀))
    r_squared = coeff * (1 - p0) / (available_per_arm * p0)
    r = r_squared ** 0.5
    return r * 100.0  # back to percent


def assess_feasibility(
    *,
    monthly_traffic: int,
    time_window_days: int,
    baseline_rate_pct: float,
    desired_lift_pct: float,
    n_arms: int = 2,
) -> FeasibilityVerdict:
    """Can we run this test at this volume in this time and detect this lift?

    Returns a verdict explaining the math in plain language.
    """
    daily_traffic = monthly_traffic / 30.0
    total_window_traffic = daily_traffic * time_window_days
    available_per_arm = int(total_window_traffic / n_arms)

    needed_per_arm = sample_size_per_arm(
        baseline_rate_pct=baseline_rate_pct,
        relative_lift_pct=desired_lift_pct,
    )

    feasible = available_per_arm >= needed_per_arm
    detectable = detectable_lift(
        baseline_rate_pct=baseline_rate_pct,
        available_per_arm=available_per_arm,
    )

    if feasible:
        reason = (
            f"OK: {available_per_arm:,} available/arm ≥ {needed_per_arm:,} needed/arm "
            f"to detect +{desired_lift_pct:.1f}% lift on {baseline_rate_pct:.1f}% baseline."
        )
    else:
        reason = (
            f"INSUFFICIENT: {available_per_arm:,} available/arm < {needed_per_arm:,} needed/arm. "
            f"With this traffic ({monthly_traffic:,}/month, {time_window_days}d window) "
            f"you can only detect lifts ≥ {detectable:.1f}% on {baseline_rate_pct:.1f}% baseline."
        )

    return FeasibilityVerdict(
        feasible=feasible,
        needed_per_arm=needed_per_arm,
        available_per_arm=available_per_arm,
        detectable_relative_lift_pct=round(detectable, 2),
        reason=reason,
    )
