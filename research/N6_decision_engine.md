# Node N6 — Decision Engine Research

> Generated: 2026-04-27
> Scope: Take agent_findings + agent_proposals (N5) + market patterns (N3) + historical learnings (N8) → apply priority formula → ranked top-K hypotheses with explainable score breakdown.

---

## TL;DR

For day-1, **build the formula directly in Python — do not pull in PyMCDM or scikit-criteria**. Our v1 weighted-sum is a textbook MCDM "Weighted Sum Model (WSM)" with 6 criteria; wrapping it in a 200-class library buys nothing and obscures explainability. The libraries become attractive only if/when we want to A/B-test alternative aggregation methods (TOPSIS, VIKOR, PROMETHEE) — that is a v2 conversation.

For **explainability**, do not import SHAP. SHAP exists because ML models are opaque; our formula is already additive and linear, so per-criterion contribution `weight_i * normalized_value_i` IS the Shapley value (this is the well-known "linear model = exact Shapley" result). Build a small `ScoreExplanation` dataclass that emits the breakdown in plain English and renders as a bar/waterfall chart in the UI.

For **calibration** under sparse ground truth: use Beta-Binomial conjugate priors per (industry × pattern_type) bucket, weak/uniform on day 1, updated post-experiment. Combine with **simulation-based calibration (SBC)** to validate the formula even before real test results land.

For the **CRO-tool prior art**: PIE (Goward), ICE (Sean Ellis) and PXL (Peep Laja / CXL) are the canonical formulas — our v1 is essentially PXL's spirit (objective, decomposable) with weights from PIE's intuition. AB Tasty's "EVI" and Unbounce "Smart Traffic" are the closest commercial analogues; both are black boxes to users — that is exactly the gap an explainable formula fills.

**Bandits, Pareto fronts, AHP**: defer all three. Bandit selection is a runtime A/B traffic-allocation concern (different node), Pareto is worth surfacing as a secondary "trade-off hint" but not as the primary ranker, and AHP's pairwise overhead (15 questions for 6 criteria) is unjustified when we already have weights.

**Recommended starter set**: stdlib + `pydantic` + `pyyaml` + `scipy.stats` (Beta) + `rich` (CLI breakdown rendering). Total new deps: 2 (`pyyaml` and `rich` — `pydantic` and `scipy` are almost certainly already in N1/N5).

---

## Top 5 existing solutions

### 1. PyMCDM (v1.4.x, 2025)
A research-grade library implementing 30+ MCDA methods (TOPSIS, VIKOR, COPRAS, EDAS, MABAC, MAIRCA, PROMETHEE, ELECTRE, WSM, WPM, WASPAS) plus normalization/weighting helpers (entropy, CRITIC, MEREC, AHP). Ships with Pareto-front utilities and rank-correlation diagnostics.
- **Strengths**: huge method coverage, good for sensitivity analysis ("would TOPSIS rank our top-K differently from WSM?").
- **Weaknesses**: opinionated decision-matrix API (numpy 2-D arrays + criteria-direction vectors); criteria/weight arrays decoupled from semantic names — bad for explainability messages.
- **Verdict**: pull in **only** if we add a v1.1 "alternative-aggregation sensitivity" feature.

### 2. scikit-criteria (v0.9, 2025)
A "scikit-learn-shaped" MCDA toolkit. Pipeline-style API (`Pipeline([invert_min, scale_max, weight_sum])`) feels familiar to ML engineers and produces a `Result` object with rank + score breakdown.
- **Strengths**: pipelines compose cleanly; exposes per-step intermediate values (good for explainability).
- **Weaknesses**: smaller method set than PyMCDM; semi-active maintenance; documentation gaps around custom normalizers.
- **Verdict**: best library if we ever need to *outsource* the formula — but our weights are too few/explicit to need it on day 1.

### 3. PXL framework (CXL / Speero)
Not a library — a methodology. Replaces subjective ICE/PIE 1–10 scales with binary yes/no questions ("change above the fold?", "noticeable in 5 s?", "based on user research?"), summed into a score. Industry reference for *evidence-quality* prioritization in CRO.
- **Why it matters**: validates our `evidence_strength` and `goal_alignment` decomposition; gives us a vocabulary CRO-savvy users already know.

### 4. AB Tasty EVI ("Evi Ideas") + Unbounce Smart Traffic
Closest commercial analogues. EVI scans a page, generates ideas, and ranks them; Smart Traffic dynamically routes to the best variant post-launch (bandit-flavoured). Both are black boxes — users see a number, not a breakdown.
- **Why it matters**: the *gap* — no explainable score breakdown, no per-criterion attribution — is exactly our differentiator. Document this in the user-facing UI.

### 5. Optuna's `MultiObjectiveStudy` + `pareto_front`
Tangentially relevant. Hyperparameter library, but its Pareto-front API is the cleanest Python implementation we found for surfacing trade-offs ("variant A: +12% CR / -3% AOV vs variant B: +4% CR / +9% AOV"). Worth lifting the *pattern*, not the dependency.

---

## Code references worth studying

| Reference | What to look at | Why |
|---|---|---|
| `PyMCDM.weights.entropy_weights` | Entropy-based weight derivation | Future use for auto-deriving weights from historical decision_runs once we have data |
| `scikit-criteria.agg.simple.WeightedSumModel` | `_evaluate_data` method | Cleanest reference for per-alternative score with intermediate state |
| `shap.Explanation` dataclass | Field layout (values, base_values, data, feature_names) | Mirror the API for our `ScoreExplanation` — frontends/notebooks expect this shape |
| `MLflow Model.log_params` + `log_metric` | Per-run trace structure | Pattern for our `decision_run.jsonl` audit log |
| `pydantic-settings` YAML loader | Versioned, validated config | Direct fit for our `formula_config.yaml` |
| `scipy.stats.beta` | Conjugate update for binary outcomes | Backbone of N8 feedback loop |
| Optuna `study.best_trials` (multi-obj) | Returns Pareto front | Pattern for surfacing trade-off hypotheses |
| LangChain `RunnableLambda` + `add_message` traces | Structured intermediate logging | Pattern for capturing inputs/sub-scores per decision_run |

---

## Production case studies

There is **no public, detailed write-up of how AB Tasty / Unbounce / Mutiny / Convertize internally rank AI-generated suggestions** — they all treat ranking as proprietary. What we *do* know:

- **AB Tasty EVI** publicly says it "turns concepts into buildable experiments" and "predicts impact" — strongly implies a regression model trained on past test results, plus an LLM scoring layer. No formula disclosed.
- **Unbounce Smart Traffic** is explicitly a contextual bandit (announced 2018; updated to deep model in 2022) — it allocates *traffic*, not *ideas*. Out of scope for N6.
- **Convertize** historically did not auto-rank — it has a static library of 250 neuromarketing tactics with manual filters.
- **CXL/Speero** publish PXL but do not run it programmatically — it's a spreadsheet at most clients.

The closest *open* prior art is the PIE/ICE/PXL family (transparent formulas) and the academic MCDM literature (transparent algorithms). This is the right side of the build/buy line for us — there is no library shaped like our problem because our problem (LLM-generated CRO hypotheses + multi-agent confidence + CRO-domain weights) is novel.

---

## Build vs buy verdict

**Build, with patterns borrowed from libraries — do not depend on a library.**

Reasons:
1. **Six criteria, additive formula**: a 30-line `priority_score()` function. A library wrapper would be > the library's value.
2. **Explainability is the product**: every external library obscures the per-step math behind its own abstractions. Owning the code lets us emit perfect natural-language breakdowns.
3. **Versioning the formula** is critical for N8 feedback. We need to control the wire format of `decision_run` records — a library upgrade should never silently change historical scores.
4. **YAML-driven weights** are trivial to wire ourselves; libraries either don't expose weight injection cleanly or assume CSV decision-matrix inputs.
5. **Future-proofing**: when/if we want TOPSIS sensitivity analysis or entropy-derived weights, *then* drop in PyMCDM as a *secondary* pathway — keep the primary path stdlib.

The only library we'd pull in unconditionally is `pyyaml` for config and `pydantic` for the schema (both already justified by N1/N5).

---

## Concrete patterns to copy

### A) Complete priority formula implementation (sub-functions)

```python
# src/decision_engine/scoring.py
"""
Priority scoring for ranked hypotheses (Node N6).

Each sub-score is in [0.0, 1.0]. Final priority_score is in [0.0, 1.0]
and rendered to UI as score * 10 (so "8.2 / 10").
"""
from __future__ import annotations
from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Iterable


# ---------- sub-score functions (each pure, testable, swappable) -------------

def impact_signal(
    proposal_predicted_lift: float | None,   # e.g. 0.07 = +7% CR
    market_pattern_avg_lift: float | None,   # from N3 retrieval
    historical_lift_for_similar: float | None,  # from N8 (None on day 1)
) -> float:
    """
    Blend predicted impact from agents + market priors + history.
    Maps a lift estimate (a proportion) onto [0,1] via a soft cap at +25%.
    Unknowns contribute 0.5 (neutral).
    """
    signals = []
    for s in (proposal_predicted_lift, market_pattern_avg_lift, historical_lift_for_similar):
        if s is None:
            continue
        signals.append(min(max(s / 0.25, 0.0), 1.0))
    if not signals:
        return 0.5  # graceful unknown
    return sum(signals) / len(signals)


def evidence_strength(
    citations: list["Citation"],   # has .tier in {1,2,3} and .relevance in [0,1]
) -> float:
    """
    Authority-weighted evidence (Tier1=1.0, Tier2=0.7, Tier3=0.4),
    diminishing returns past 3 citations.
    """
    tier_weight = {1: 1.0, 2: 0.7, 3: 0.4}
    if not citations:
        return 0.3  # weak default — not 0.5, because *no* evidence is a real signal
    weighted = sum(tier_weight[c.tier] * c.relevance for c in citations[:5])
    # 3 strong citations saturate the score
    return min(weighted / 3.0, 1.0)


def goal_alignment(
    hypothesis_target_metric: str,
    user_primary_goal: str,
    secondary_goals: list[str],
) -> float:
    """
    1.0 if hypothesis directly targets the user's primary KPI,
    0.6 if it targets a declared secondary,
    0.3 otherwise.
    """
    if hypothesis_target_metric == user_primary_goal:
        return 1.0
    if hypothesis_target_metric in secondary_goals:
        return 0.6
    return 0.3


def agent_agreement(votes: list["AgentVote"]) -> float:
    """
    Confidence-weighted consensus across N5 agents.
    1.0 = all agents agree with high confidence; 0.0 = total disagreement.
    Uses 1 - normalized weighted std of recommendation scores.
    """
    if len(votes) < 2:
        return 0.5
    weights = [v.confidence for v in votes]
    scores = [v.recommendation_score for v in votes]  # each in [0,1]
    w_mean = sum(w * s for w, s in zip(weights, scores)) / sum(weights)
    w_var = sum(w * (s - w_mean) ** 2 for w, s in zip(weights, scores)) / sum(weights)
    w_std = w_var ** 0.5
    # std of [0,1] uniform is ~0.289 — use that as the "max disagreement"
    return max(0.0, 1.0 - (w_std / 0.289))


def risk(
    affects_pricing: bool,
    affects_legal_copy: bool,
    affects_brand_voice: bool,
    historical_failure_rate_for_pattern: float | None,  # None on day 1
) -> float:
    """
    Higher = riskier. Each high-stakes flag adds risk; history can override.
    """
    base = 0.0
    if affects_pricing:        base += 0.4
    if affects_legal_copy:     base += 0.5
    if affects_brand_voice:    base += 0.2
    if historical_failure_rate_for_pattern is not None:
        base = max(base, historical_failure_rate_for_pattern)
    return min(base, 1.0)


def implementation_complexity(
    estimated_dev_hours: float,
    requires_backend: bool,
    requires_design: bool,
) -> float:
    """
    Higher = harder. 0–8h ≈ 0.2, 8–24h ≈ 0.5, 24h+ ≈ 0.8 baseline.
    """
    if estimated_dev_hours <= 8:
        base = 0.2
    elif estimated_dev_hours <= 24:
        base = 0.5
    else:
        base = 0.8
    if requires_backend: base += 0.15
    if requires_design:  base += 0.05
    return min(base, 1.0)


# ---------- aggregator -------------------------------------------------------

@dataclass(frozen=True)
class FormulaWeights:
    impact_signal: float = 0.30
    evidence_strength: float = 0.20
    goal_alignment: float = 0.20
    agent_agreement: float = 0.15
    risk: float = -0.10                    # negative — penalty
    implementation_complexity: float = -0.05  # negative — penalty
    formula_version: str = "1.0.0"

    def __post_init__(self):
        # weights of *positive* terms must sum to 1; penalties separate
        positives = (
            self.impact_signal + self.evidence_strength
            + self.goal_alignment + self.agent_agreement
        )
        assert abs(positives - 1.0) < 1e-9, f"Positive weights must sum to 1.0, got {positives}"


@dataclass(frozen=True)
class SubScores:
    impact_signal: float
    evidence_strength: float
    goal_alignment: float
    agent_agreement: float
    risk: float
    implementation_complexity: float


@dataclass(frozen=True)
class ScoreExplanation:
    final_score: float            # in [0, 1]
    final_score_display: float    # final_score * 10
    sub_scores: SubScores
    contributions: dict[str, float]   # weight * sub_score per term
    weights: FormulaWeights
    formula_version: str
    confidence_penalty: float     # extra penalty when many sub-scores fell back to defaults
    used_defaults: list[str]      # which fields used the 0.5 fallback


def compute_priority(
    sub: SubScores,
    weights: FormulaWeights,
    used_defaults: list[str] | None = None,
) -> ScoreExplanation:
    used_defaults = used_defaults or []
    contributions = {
        "impact_signal":             weights.impact_signal * sub.impact_signal,
        "evidence_strength":         weights.evidence_strength * sub.evidence_strength,
        "goal_alignment":            weights.goal_alignment * sub.goal_alignment,
        "agent_agreement":           weights.agent_agreement * sub.agent_agreement,
        "risk":                      weights.risk * sub.risk,
        "implementation_complexity": weights.implementation_complexity * sub.implementation_complexity,
    }
    raw = sum(contributions.values())
    # graceful unknown handling: penalize confidence when we leaned on defaults
    confidence_penalty = 0.05 * len(used_defaults)
    final = max(0.0, min(1.0, raw - confidence_penalty))
    return ScoreExplanation(
        final_score=final,
        final_score_display=round(final * 10, 1),
        sub_scores=sub,
        contributions=contributions,
        weights=weights,
        formula_version=weights.formula_version,
        confidence_penalty=confidence_penalty,
        used_defaults=used_defaults,
    )
```

### B) Score-breakdown explanation generator (the "this scored 8.2 because..." sentence)

```python
# src/decision_engine/explain.py
from .scoring import ScoreExplanation

_LABELS = {
    "impact_signal":             "predicted impact",
    "evidence_strength":         "evidence quality",
    "goal_alignment":            "alignment with your goal",
    "agent_agreement":           "agent consensus",
    "risk":                      "risk",
    "implementation_complexity": "implementation effort",
}


def to_sentence(exp: ScoreExplanation) -> str:
    # rank contributions by absolute magnitude
    ranked = sorted(exp.contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_pos = [(k, v) for k, v in ranked if v > 0][:3]
    top_neg = [(k, v) for k, v in ranked if v < 0][:2]

    parts = [f"This scored {exp.final_score_display}/10 because"]
    parts += [f"{_LABELS[k]} contributed +{v*10:.1f}" for k, v in top_pos]
    if top_neg:
        parts.append("offset by")
        parts += [f"{_LABELS[k]} {v*10:+.1f}" for k, v in top_neg]
    if exp.used_defaults:
        parts.append(
            f"(confidence reduced by {exp.confidence_penalty*10:.1f} — missing data for: "
            f"{', '.join(exp.used_defaults)})"
        )
    return ", ".join(parts) + "."


def to_waterfall_rows(exp: ScoreExplanation) -> list[dict]:
    """For UI rendering (e.g. Plotly waterfall, Recharts bar)."""
    return [
        {"factor": _LABELS[k], "delta": round(v * 10, 2), "is_penalty": v < 0}
        for k, v in exp.contributions.items()
    ]
```

### C) Configurable weights YAML pattern

```yaml
# config/formula_v1.yaml
formula_version: "1.0.0"
weights:
  impact_signal: 0.30
  evidence_strength: 0.20
  goal_alignment: 0.20
  agent_agreement: 0.15
  risk: -0.10
  implementation_complexity: -0.05

evidence_tiers:
  tier_1_real_test_result:    1.0
  tier_2_user_curated:        0.7
  tier_3_external_blog_post:  0.4

defaults:
  impact_when_unknown:        0.5
  agreement_when_single_agent: 0.5
  evidence_when_no_citations: 0.3   # *not* 0.5 — absence is a real negative signal
  confidence_penalty_per_default: 0.05

ranking:
  top_k:                  10
  min_score_to_recommend: 0.45
  pareto_hint:            true   # also surface non-dominated alternatives
```

```python
# src/decision_engine/config.py
import yaml
from pathlib import Path
from .scoring import FormulaWeights

def load_formula(path: Path) -> FormulaWeights:
    raw = yaml.safe_load(path.read_text())
    w = raw["weights"]
    return FormulaWeights(
        impact_signal=w["impact_signal"],
        evidence_strength=w["evidence_strength"],
        goal_alignment=w["goal_alignment"],
        agent_agreement=w["agent_agreement"],
        risk=w["risk"],
        implementation_complexity=w["implementation_complexity"],
        formula_version=raw["formula_version"],
    )
```

### D) `decision_run` schema (audit log + calibration source)

```python
# src/decision_engine/audit.py
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Any

class DecisionRunRecord(BaseModel):
    """One per ranking call. Append-only JSONL. Source of truth for N8."""
    decision_run_id: str               # uuid4
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    formula_version: str
    weights_snapshot: dict[str, float]
    inputs_hash: str                   # sha256 of canonicalized agent_findings + proposals
    user_goal: str
    secondary_goals: list[str]
    industry: str
    proposals: list[dict[str, Any]]    # full per-proposal: sub_scores, contributions, final
    top_k_ids: list[str]
    pareto_front_ids: list[str]
    runtime_ms: int
    git_sha: str | None = None         # of the running code

    def write(self, path: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(self.model_dump_json() + "\n")
```

This schema is **the** integration contract with N8. Never break it without bumping `formula_version`.

### E) Calibration update pattern (Beta-Binomial, sparse-data safe)

```python
# src/decision_engine/calibration.py
"""
Bayesian calibration of impact_signal per (industry, pattern_type) bucket.
Day 1: weak prior Beta(2, 8) — mean 0.2 (20% lift hypothesis ~rare to win).
On each completed test result from N8, conjugate-update.
"""
from dataclasses import dataclass
from scipy.stats import beta

@dataclass
class BucketPrior:
    industry: str
    pattern_type: str
    alpha: float = 2.0    # successes + 1
    beta_param: float = 8.0  # failures + 1

    def expected_win_rate(self) -> float:
        return self.alpha / (self.alpha + self.beta_param)

    def credible_interval_95(self) -> tuple[float, float]:
        return beta.ppf(0.025, self.alpha, self.beta_param), beta.ppf(0.975, self.alpha, self.beta_param)

    def update(self, won: bool) -> "BucketPrior":
        return BucketPrior(
            industry=self.industry,
            pattern_type=self.pattern_type,
            alpha=self.alpha + (1 if won else 0),
            beta_param=self.beta_param + (0 if won else 1),
        )


def adjust_impact_with_prior(
    raw_impact: float,
    prior: BucketPrior,
    n_total_tests_for_bucket: int,
) -> tuple[float, float]:
    """
    Shrink raw_impact toward the bucket's expected win rate, with shrinkage
    proportional to data sparsity. Returns (adjusted_impact, shrinkage_factor).
    """
    # Shrinkage factor: 1.0 when no data, 0.0 when ≥30 tests
    shrinkage = max(0.0, 1.0 - n_total_tests_for_bucket / 30.0)
    posterior_mean = prior.expected_win_rate()
    adjusted = (1 - shrinkage) * raw_impact + shrinkage * posterior_mean
    return adjusted, shrinkage
```

This is the bridge from N8 (test results) → N6 (next ranking). Day 1: every bucket starts at `Beta(2,8)`, so impact_signal is shrunk strongly toward 0.2. Day 90: buckets with > 30 tests rely on the raw signal.

### F) Pareto-front hint (secondary surface, not primary ranker)

```python
# src/decision_engine/pareto.py
from .scoring import ScoreExplanation

def pareto_front(
    proposals: list[tuple[str, ScoreExplanation, dict[str, float]]],
    # objectives: dict like {"predicted_cr_lift": 1, "predicted_revenue_lift": 1, "risk": -1}
    objectives: dict[str, int],
) -> list[str]:
    """
    Return ids of non-dominated proposals on the given objectives.
    Used to flag "this scored lower overall but is the only one that maximizes revenue".
    """
    front = []
    for i, (pid_i, _, m_i) in enumerate(proposals):
        dominated = False
        for j, (pid_j, _, m_j) in enumerate(proposals):
            if i == j:
                continue
            ge_all = all(
                m_j[k] * d >= m_i[k] * d for k, d in objectives.items()
            )
            gt_any = any(
                m_j[k] * d > m_i[k] * d for k, d in objectives.items()
            )
            if ge_all and gt_any:
                dominated = True
                break
        if not dominated:
            front.append(pid_i)
    return front
```

Show Pareto-front IDs in UI as a "trade-off" badge on hypotheses *outside* the top-K.

---

## Anti-patterns

1. **Don't normalize sub-scores after weighting.** A common bug: `final = sum(contributions) / sum(abs(weights))`. This destroys the natural [0,1] interpretation and makes risk penalties meaningless.
2. **Don't use SHAP / LIME for this.** It's overkill — for an additive linear formula, contribution = weight × value IS the Shapley value. Importing `shap` adds 200 MB of deps and a misleading "ML interpretability" framing.
3. **Don't treat "missing data" as 0.** Treat it as 0.5 (neutral) plus a `confidence_penalty`. Treating absence as zero would crush every brand-new hypothesis pattern.
4. **Don't average agent_agreement naively.** Use confidence-weighted variance — three confident agents agreeing should beat five unconfident ones.
5. **Don't bake weights into Python source.** YAML-driven, formula_version-stamped. Otherwise you cannot A/B-test formula changes (Q9).
6. **Don't compute Pareto fronts on the priority_score alone.** Pareto requires *raw* objectives (CR lift, revenue lift, risk), not the aggregated score — a single scalar has a trivial Pareto front of size 1.
7. **Don't rebalance weights based on outliers.** If one industry tested 100 hypotheses and another tested 3, weighting by raw counts in N8 → N6 retraining will overfit. Use the bucketed Beta priors above instead.
8. **Don't expose the formula as the ranking, expose the breakdown as the ranking.** The number is a header; the bar chart of contributions is the UI. Otherwise users push back without context ("why is this 8.2?") and trust collapses.
9. **Don't try to use AHP for our 6 criteria.** 15 pairwise comparisons per re-weight × per user; we already have intuited weights. Defer.
10. **Don't run a multi-armed bandit over hypotheses at decision time.** MAB is a *traffic-allocation* algorithm; here we are *picking what to test*. Conflating the two leads to "the bandit converged on never showing the new idea" failure mode.

---

## Recommended starter library set

| Lib | Use | Status |
|---|---|---|
| `pydantic` >= 2.6 | Schemas (DecisionRunRecord, AgentVote, Citation) | Already in N1/N5 |
| `pyyaml` >= 6 | Config loading | New (~1 dep) |
| `scipy` >= 1.13 | `scipy.stats.beta` for calibration priors | Likely already pulled by N8/N3 |
| `rich` >= 13 | CLI rendering of breakdowns (waterfall tables) | New (~1 dep, optional) |
| `numpy` | Pareto math for >>10 proposals | Almost certainly already in deps |

**Explicitly NOT pulling in:** PyMCDM, scikit-criteria, SHAP, LIME, AHPy, pymoo, Optuna, scikit-learn (until N8 grows ML).

---

## Open verifications

1. **Empirically validate v1 weights (3-month watch)**: log every `decision_run` and every test outcome. After 50 completed tests, fit a logistic regression `won ~ sub_scores` and compare its learned weights to ours. If `impact_signal` learned coefficient is < 0.10 vs our 0.30, we are over-trusting predicted lift.
2. **Inter-agent agreement formula sanity-check**: run a synthetic test where 2 agents are perfectly correlated and a 3rd is random. Confirm `agent_agreement` returns ~0.5, not ~0.7.
3. **Confidence penalty calibration**: 0.05/missing-default is a guess. Instrument and revisit at 50-runs mark.
4. **Pareto vs WSM rank correlation**: on real data, do non-dominated proposals overlap with top-K? If yes, drop Pareto hint (redundant). If < 30% overlap, escalate Pareto to a co-equal surface.
5. **Authority-weight tier ratios (1.0/0.7/0.4)**: tier 3 may need to be 0.2 if external blogs are very noisy. Validate after first 20 hypotheses with mixed-tier evidence.
6. **Formula-version A/B test design (Q9)**: simplest defensible approach is "split decision_runs randomly between v1.0.0 and v1.1.0 for 4 weeks, compare downstream test win rate". Real ground truth is slow but inevitable. Document the experimental design before shipping v1.1.
7. **Confirm AHP defer is correct**: if/when we onboard a customer with > 3 internal stakeholders who want to set their own weights, AHP becomes valuable for resolving stakeholder conflict. Until then — defer.
8. **Confirm bandit defer is correct**: bandit *selection* is wrong (see anti-pattern #10), but a *Thompson-sampling tiebreaker* among equally-scored top-K hypotheses to inject exploration is interesting at v1.2. Park as future research.
9. **Test SBC pipeline before any real data**: simulate (parameter draw → fake test results → posterior update → check coverage). A clean SBC validates the calibration math is right *before* we have real outcomes — critical given the slow feedback loop.

---

## Sources

- [pymcdm on PyPI](https://pypi.org/project/pymcdm/)
- [pymcdm — universal MCDM library (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S235271102300064X)
- [scikit-criteria on PyPI](https://pypi.org/project/scikit-criteria/)
- [scikit-criteria documentation](https://app.readthedocs.org/projects/scikit-criteria/downloads/pdf/latest/)
- [pyDecision MCDA library](https://github.com/Valdecy/pyDecision)
- [Interpretable ML Book — SHAP chapter (Christoph Molnar)](https://christophm.github.io/interpretable-ml-book/shap.html)
- [SHAP documentation — introduction to Shapley values](https://shap.readthedocs.io/en/latest/example_notebooks/overviews/An%20introduction%20to%20explainable%20AI%20with%20Shapley%20values.html)
- [On the failings of Shapley values for explainability (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0888613X23002438)
- [Validating Bayesian Inference with Simulation-Based Calibration (Talts et al., 2018)](https://arxiv.org/pdf/1804.06788)
- [SBC R package and docs](https://hyunjimoon.github.io/SBC/)
- [Sensitivity Analyses for Sparse-Data Problems with Weakly Informative Priors (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3607322/)
- [Bayesian A/B Testing primer — Convert.com](https://www.convert.com/blog/a-b-testing/bayesian-statistics-primer-for-ab-testing/)
- [PXL framework — CXL](https://cxl.com/blog/better-way-prioritize-ab-tests/)
- [PXL framework — Speero blueprint](https://speero.com/blueprints/evolve-your-prioritization)
- [ICE vs PIE vs PXL comparison — TestBuddy](https://www.testbuddy.dev/blog/ice-pie-pxl-prioritization-frameworks-guide)
- [PIE framework — Conversion.com](https://conversion.com/framework/pie-framework/)
- [How to pick a prioritisation framework — RICE / ICE / PIE / PXL / HIPE](https://growthmethod.com/prioritisation-frameworks/)
- [AB Tasty EVI product page](https://www.abtasty.com/evi/)
- [AB Tasty — How AI Transforms Experimentation](https://www.abtasty.com/blog/how-ab-tasty-ai-transforms-experimentation/)
- [Convertize — A/B testing tools roundup](https://www.convertize.com/ab-testing-tools/)
- [Unbounce — CRO software/tools (Smart Traffic context)](https://unbounce.com/conversion-rate-optimization/cro-software-tools/)
- [Mutiny / personalization context — Guideflow CRO tools 2026](https://www.guideflow.com/blog/best-cro-tools)
- [Pareto front — Wikipedia](https://en.wikipedia.org/wiki/Pareto_front)
- [Multi-objective optimization — Wikipedia](https://en.wikipedia.org/wiki/Multi-objective_optimization)
- [R-method for ranking Pareto-optimal solutions (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2666222121000058)
- [Trade-off ranking method for MCDA (Manchester preprint)](https://personalpages.manchester.ac.uk/staff/s.utyuzhnikov/Papers/JMCA_NJSU2017.pdf)
- [Analytic Hierarchy Process — Wikipedia](https://en.wikipedia.org/wiki/Analytic_hierarchy_process)
- [AHP overhead and pairwise count — 1000minds guide](https://www.1000minds.com/decision-making/analytic-hierarchy-process-ahp)
- [Thompson sampling — Wikipedia](https://en.wikipedia.org/wiki/Thompson_sampling)
- [Multi-Armed Bandit testing — VWO glossary](https://vwo.com/glossary/multi-armed-bandit-testing/)
- [When to do bandit tests — CXL](https://cxl.com/blog/bandit-tests/)
- [Confidence-Weighted Voting / WMV overview — Emergent Mind](https://www.emergentmind.com/topics/weighted-majority-voting-wmv)
- [Beyond Majority Voting: Higher-Order LLM Aggregation (arXiv 2510.01499)](https://arxiv.org/abs/2510.01499)
- [Confidence Calibration via Multi-Agent Deliberation (arXiv 2404.09127)](https://arxiv.org/html/2404.09127v1)
- [Versioning, Provenance, and Reproducibility in Production ML — Kästner](https://ckaestne.medium.com/versioning-provenance-and-reproducibility-in-production-machine-learning-355c48665005)
- [MLOps versioning best practices — phData](https://www.phdata.io/blog/how-to-effectively-version-control-your-machine-learning-pipeline/)
- [MLflow data versioning — lakeFS](https://lakefs.io/blog/mlflow-data-versioning/)
