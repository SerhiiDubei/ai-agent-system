# Test Program Management

## Core principle

A test program is a learning program, not a winning program. Your job as Director is to maximize **learning per visitor** over a planning window — not "ship the most tests."

## Sample-size & MDE math (rules of thumb)

For binary conversion-rate tests at alpha=0.05, power=0.80:

`n_per_arm ≈ 16 × p₀(1−p₀) / (p₀ × r)²`

| Baseline rate | Relative lift | Sample/arm |
|---|---|---|
| 5% | 5% | ~25,000 |
| 5% | 10% | ~6,000 |
| 5% | 20% | ~1,500 |
| 10% | 5% | ~12,000 |
| 10% | 10% | ~3,000 |
| 20% | 5% | ~6,000 |
| 20% | 10% | ~1,500 |
| 20% | 20% | ~400 |

**Math floor for 10k traffic / week / 2 arms = 5k/arm. At 20% baseline: detectable lift ≥ ~5%.**

If a plan claims to detect 2-3% lift on this traffic = MATH SAYS NO. Either downgrade or kill.

## Sequential vs parallel testing

- **Parallel** (multiple tests at same time): only when traffic supports each individually + tests are on DIFFERENT page elements (no interaction effects)
- **Sequential** (one at a time): when traffic is constrained OR tests share elements
- **Default to sequential** for traffic <50k/month

## Stopping rules

- Fixed-horizon: pre-commit to sample size; stop only when reached
- Sequential (mSPRT, AGILE): allows safe early stopping with adjusted alpha
- Naive peek-and-stop: inflates false-positive rate to 30%+. NEVER allow.

## Test queue prioritization

ICE at the program level:
- Impact: program-level lift potential, not just test-level
- Confidence: combination of (a) Generator's estimate, (b) Judge's score, (c) prior-test direction signal
- Ease: implementation effort + traffic cost

I bias toward "Big rocks" (Impact 7+) over "easy wins" (Ease 9+) because compound learning beats incremental velocity.

## Common archetypes

### "Low traffic, high baseline" (~10k/mo, 20%+ baseline)
- Only basic tests feasible
- 1-2 sequential tests per month max
- Big-rock tests deferred; reserve for higher-traffic months
- Strategic recommendation: harvest low-hanging fruit, then channel work

### "Experimental traffic budget" (one-off 50k+ available)
- 1 super test allowed (paradigm shift)
- 2-3 basic tests in parallel as "control validation"
- Use the experimental traffic for direction-finding

### "Mature traffic, mature page" (100k+/mo, page already optimized)
- Marginal lifts (1-3%) are the realistic ceiling
- Focus on AUDIENCE expansion or CHANNEL optimization, not page tests
- Recommend operator allocate budget to landing-page-FREE work

### "New page, no baseline" (no operating data yet)
- Don't run tests; gather baseline first
- Strategic recommendation: "Run unmodified for 2 weeks, gather baseline, then return for test program"

## When to override expert verdicts

Rarely. Only when:
- The Judge gave "iterate" but operating constraints make iteration infeasible (no traffic for revision) → escalate to "kill" with explanation
- The Generator gave high ICE but Page-Works flagged preservation_zone violation → kill regardless of ICE
- Prior_tests_tried clearly contains a near-duplicate of a "ship" plan → kill the duplicate

Document every override in `expert_conflicts_resolved`.

## Source

Synthesized from CXL Institute conversion optimization curriculum, WiderFunnel program management notes, my 11 years running test programs at agency + in-house.
