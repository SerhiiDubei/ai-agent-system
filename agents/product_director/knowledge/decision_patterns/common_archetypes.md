# Common Decision Archetypes

These are the recurring decision patterns I see in test programs. Each archetype names: the operating fingerprint, the right Director response, and what the strategic recommendation should sound like.

---

## Archetype A — "Low-traffic, high-baseline working page"
**Fingerprint:** ≤15k/mo traffic, ≥18% baseline conversion, page is already working.

**Right response:**
- Ship 1 sequential test per cycle (not parallel)
- Only basic tests (single-element changes)
- Reject any plan needing >5k visitors per arm
- Defer all advanced/expert/super tests

**Strategic recommendation template:**
*"This page is mature and traffic-constrained. Expect 2-5% lifts max from page tests this cycle. Recommend operator focus next quarter's investment on audience expansion (lookalike seeds, new segments) rather than page-level testing — bigger ROI lever."*

---

## Archetype B — "Mid-traffic, mid-baseline, optimization room"
**Fingerprint:** 30-100k/mo, 5-15% baseline, page has been optimized but has obvious gaps.

**Right response:**
- 2-3 tests per cycle, parallel-safe if on different elements
- Mix basic (2) + advanced (1)
- One big-rock test allowed per quarter

**Strategic recommendation template:**
*"Traffic supports a faster test cadence. Next batch should explore the [specific gap from Page-Works analysis]. Recommend rotating focus across page sections — this batch focuses on hero, next batch should look at form/below-fold."*

---

## Archetype C — "High-traffic, broken or unknown page"
**Fingerprint:** 100k+/mo, conversion rate uncertain or below industry benchmark for archetype.

**Right response:**
- 1 super test (paradigm shift) for direction-finding
- 2-3 basic tests in parallel as control-pattern validation
- Aggressive timeline (results in 2 weeks)

**Strategic recommendation template:**
*"Page may be fundamentally mismatched to audience. Super test on [offer/format/persona-targeting] will tell us whether incremental optimization or fundamental redesign is the path. Recommend operator hold next-batch budget until super test verdict."*

---

## Archetype D — "Brand-new page, no baseline"
**Fingerprint:** New launch, no historical conversion data.

**Right response:**
- Don't ship tests yet
- Defer all plans
- Recommend 2-week baseline-gathering period

**Strategic recommendation template:**
*"No baseline data yet. Recommend running unmodified for [2-4 weeks] to gather conversion baseline + traffic patterns. Return with operating data, then run focused test program."*

---

## Archetype E — "Constrained time window"
**Fingerprint:** ≤7-day window for testing (e.g. campaign with hard deadline).

**Right response:**
- Only basic tests (low risk, fast signal)
- Aggressive sample-size pre-check
- 1-2 tests max
- No big-rock tests (too risky in compressed window)

**Strategic recommendation template:**
*"7-day window forces conservative testing. Ship 1-2 basic tests with high prior confidence. Recommend operator pre-commit to next month's traffic for the bigger tests in the queue — they need the runway."*

---

## Archetype F — "Mature operator, advanced appetite"
**Fingerprint:** Operator has prior_tests_tried list of 10+ items, sophisticated about CRO.

**Right response:**
- Skip the obvious low-hanging tests
- Filter HG plans aggressively against prior_tests
- Allow 1 expert/super test per cycle
- Trust operator's risk_appetite="experimental"

**Strategic recommendation template:**
*"Operator has harvested obvious wins. Remaining lifts will come from non-obvious angles: [specific next-frontier suggestion]. Recommend [specific sophisticated test type] as the next program theme."*

---

## Cross-archetype rule

**Default to defer.** When in doubt, "iterate" beats "ship." A failed test costs visible traffic; a deferred test costs nothing visible but preserves future test slots.

The hardest discipline: telling an enthusiastic operator "your plan is good, but not yet shippable" — and being specific enough about WHAT to fix that the operator trusts the discipline.
