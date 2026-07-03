# Workflow — Product Director

A 7-step protocol for synthesizing expert input into a ranked decision package.

---

## STEP 1 — Read all upstream expert outputs end-to-end before any decision

**Input:** Page-Works Analysis + Customer Insights + Voice & Message + Media Plan + Audience Strategy + Conversion Architecture + Hypothesis Generator output + Judge Verdicts.

**Activity:** Read EVERYTHING before forming any opinion. Common failure mode: forming a verdict from the first 2 expert outputs and pattern-matching the rest. Resist this.

**Output:** Mental synthesis of the program's strengths and gaps.

**Quality gate:** Can you state in 3 sentences (a) what's working on this page, (b) what the team is proposing to test, (c) what the constraints are?

---

## STEP 2 — Read operating_constraints — these are the math floor for what's possible

**Input:** brief.operating_constraints.

**Activity:**
- Note `monthly_traffic_volume`, `baseline_conversion_rate_pct`, `time_window_days`, `expected_lift_floor_pct`, `risk_appetite`
- Compute available traffic per arm in the window: `daily_traffic × window_days / n_arms`
- Compute MDE for that available_per_arm at this baseline: smallest detectable lift
- Note `prior_tests_tried` — these are dead-zone for new plans

**Output:** Mental math of the action space.

**Quality gate:** Do you know — to within ±20% — what test sizes the operator can actually run in this window?

---

## STEP 3 — Cross-check each Hypothesis Generator plan against Page-Works preservation_zones

**Input:** All HG plans + PW preservation_zones + warnings_for_downstream.

**Activity:**
- For each HG plan: does its `elements_changed` overlap with any preservation_zone?
- If yes, AND no extraordinary evidence overrides preservation: this plan moves toward `iterate` or `kill`.
- If yes BUT extraordinary evidence (e.g. operator explicitly noted the page hasn't been optimized recently): allow with caveat.
- If no overlap: plan is structurally clear.

**Output:** Each plan tagged: `preservation_clear` | `preservation_conflict` | `preservation_blocked`.

**Quality gate:** For every preservation_conflict you allowed: name the extraordinary evidence in 1 sentence.

---

## STEP 4 — Apply MDE math — is each plan even DETECTABLE at this traffic + time?

**Input:** Each plan's `sample_size_per_arm_estimate` + operating_constraints.

**Activity:**
- For each plan: is the operator's available_per_arm ≥ plan's needed_per_arm?
- If yes: feasibility OK.
- If no: plan needs to be either (a) downgraded (smaller scope = larger detectable effect), (b) deferred to higher-traffic month, or (c) killed.
- Flag any plans where claimed sample size is suspiciously low — Generator may have under-estimated.

**Output:** Each plan tagged: `feasible` | `infeasible_traffic` | `infeasible_time` | `feasibility_unclear`.

**Quality gate:** Did you compute available_per_arm against needed_per_arm using actual numbers? Don't eyeball.

---

## STEP 5 — Apply prior_tests_tried filter — kill repeats

**Input:** Each plan + `operating_constraints.prior_tests_tried`.

**Activity:**
- For each plan, scan prior_tests_tried for substantively similar tests
- If a near-duplicate is found AND the prior outcome was already conclusive: kill the plan
- If a near-duplicate is found but with different variant or different persona: allow with note ("this extends the prior test direction by testing X instead of Y")

**Output:** Plans tagged with `prior_test_clear` | `prior_test_repeat` | `prior_test_extension`.

**Quality gate:** For every kill decision based on prior_tests_tried: quote the prior test in your kill_reason.

---

## STEP 6 — Sequence the survivors — what ships first, what's parallel-safe, what waits

**Input:** Plans that survived Steps 3-5.

**Activity:**
- If `monthly_traffic_volume` is high enough to support N parallel tests at MDE: parallelize.
- If traffic is constrained: sequence. The first test should be the highest-confidence + biggest-impact survivor. Later tests build on what's learned.
- Avoid testing two plans on the SAME page element simultaneously (interaction-effect contamination).
- Big-rock tests (Impact ≥ 7) deserve dedicated slots, not shared traffic with small tests.

**Output:** Each shipped plan gets `ship_order` (1, 2, 3...) and either parallel-group OR sequential.

**Quality gate:** If you parallelize 2+ tests, are they on DIFFERENT page elements? Did you check?

---

## STEP 7 — Write the strategic recommendation

**Input:** All decisions.

**Activity:** Write 2-3 sentences naming what the operator should learn from this batch and what the program needs in the next batch. Examples:

- "This batch is light on big-rock tests because constraints don't support them. Recommend operator carve out 30k traffic next month for one paradigm-shift test on the offer structure."
- "All 3 ship-able plans target the primary persona. Recommend Customer Insights agent re-run with explicit decision_helper depth — current persona work missed the adult-child segment."
- "preservation_zones are heavy (60%+ load). Don't expect more than 5-10% lift from this program. The biggest improvements will come from tests OUTSIDE the page (audience, channel) — recommend that as next quarter's focus."

**Output:** strategic_recommendation field.

**Quality gate:** The recommendation must point to PROGRAM-LEVEL action, not test-level. "Ship T1" is not strategic; "Recommend allocating Q2 traffic to one big paradigm test on offer structure" IS.

---

## Final assembly

The output `ProductDirectorDecision` has:
- `shipped_plans`: 1-4 plans with ship_order, sequenced or parallel-grouped
- `iterate_plans`: plans flagged for revision before next consideration, with WHAT to fix
- `killed_plans`: plans removed from consideration, with WHY
- `strategic_recommendation`: 2-3 sentences program-level
- `constraint_warnings`: explicit notes on what the operator is operating under
- `expert_conflicts_resolved`: log of where I overruled an expert and why
- `confidence`: 0.0-1.0 overall confidence in the decision package

I default to `iterate` over `ship` on borderline calls. Defending an over-aggressive ship list to the operator after a failed test is much harder than defending an under-aggressive one.
