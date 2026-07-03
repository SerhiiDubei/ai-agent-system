# Workflow — Page-Works Analyzer

A 5-step protocol for every page audit. Each step has explicit inputs, outputs, and a quality gate.

---

## STEP 1 — Load page context

**Input:** PageContext object (from snapshot/) + brief metadata + operating constraints (if present).

**Activity:**
- Read URL, title, meta description, page archetype (from N2 classifier)
- Read forms summary (number of fields, submit text, viewport differences)
- Read detected element roles (hero_headline, primary_cta, trust_badge, etc.)
- Read visible_copy_excerpt (first 4000 chars of markdown)
- If `operating_constraints.baseline_conversion_rate_pct` is present: this is your STARTING ASSESSMENT. ≥15% on lead capture, ≥25% on quiz, ≥3% on ecom = page is working

**Output:** Mental model of the page's structure + an initial baseline assessment (works | partial | broken | unknown).

**Quality gate:** Can you describe the page's archetype + primary CTA + form depth in one sentence? If not, page_context is incomplete — flag this in confidence.

---

## STEP 2 — Apply LIFT model in REVERSE

**Input:** Page context + brief metadata.

**Activity:** Walk LIFT (Value Proposition / Relevance / Clarity / Anxiety / Distraction / Urgency) in REVERSE — find what's WORKING on each lever, not what's broken. Score each lever 1-5:

- **5** = lever is doing heavy lifting, do not touch
- **4** = lever is solid, can test variants but expect small wins
- **3** = lever is adequate, change-safe zone
- **2** = lever is weak, reasonable test target
- **1** = lever is broken, priority test target

For each lever scoring 4-5, write 1-2 sentences naming WHY it's working. e.g. "Trust lever 5/5 because: BBB A+ above the fold + 'Since 2007' + state license number + named local installer photo. This stack addresses cold-traffic Meta scrutiny."

**Output:** Per-lever scoring + rationale for high-scoring levers.

**Quality gate:** Did you score every lever? Did you justify high scores with specific page elements? If not, you're guessing.

---

## STEP 3 — Map trust anatomy

**Input:** Step 2 output + market_segment context (load `knowledge/working_page_patterns/<segment>.md`).

**Activity:** Identify 3-5 trust mechanisms on the page and estimate their conversion-load share. Examples:

- "BBB A+ badge above-the-fold = ~20% load" (high-prominence, regulated industry)
- "Testimonial wall with 4 senior women = ~15% load" (audience self-selection signal)
- "'Since 2007 / 4,500 Florida seniors served' = ~10% load" (longevity + specific number)
- "Phone number prominently visible = ~10% load" (senior audience comfort)

Sum across mechanisms; if the trust anatomy is doing 50%+ of conversion work, this is a HIGH-PRESERVATION page. Test the working-mechanism column carefully.

**Output:** List of `TrustMechanism` items with element + estimated load_share + why-it-works rationale.

**Quality gate:** Do your load shares roughly sum to the conversion contribution you'd estimate? Calibrate against `working_page_patterns/<segment>.md` for sanity.

---

## STEP 4 — Map preservation zones vs change-safe zones

**Input:** Step 2 + Step 3 outputs.

**Activity:**

- **Preservation zones**: page elements that are LOAD-BEARING. Downstream agents must justify any test here with extraordinary evidence. Typically:
  - High-load trust mechanisms
  - The hero's value-prop wording (if it matches a working voice)
  - The form depth IF the operator's lead-quality is good
  - Any element whose presence is mandated by regulation

- **Change-safe zones**: elements that can be tested with normal evidence. Typically:
  - Microcopy on secondary CTAs
  - Image variants (if not the hero)
  - Element ORDER (within the same content)
  - Color/visual style (within accessibility constraints)
  - Anything below the fold on mobile that mostly affects scroll-completion not click-through

- Anything not classified gets `change_with_caution` — needs case-by-case justification.

**Output:** Two lists with element_id + reasoning per item.

**Quality gate:** For every element in preservation_zones, can you state in 1 sentence why it's load-bearing? If the answer is "best practice says so" — re-evaluate; that's preserving by reflex.

---

## STEP 5 — Generate explicit warnings for downstream

**Input:** All previous outputs.

**Activity:** Write 2-5 explicit `warnings_for_downstream` — these are the messages other experts (CI, Voice & Message, Conversion Architect, Hypothesis Generator) MUST consider before proposing changes. Examples:

- "DO NOT propose hero_headline rewrite without extraordinary evidence. The current headline matches the brand's awareness-stage and trust anatomy in a way that's been optimized — likely 25%+ load share."
- "Form has 4 fields but operator's lead-quality is high. DO NOT propose field reduction without evidence that conversion-quality won't suffer — the form is filtering, not just collecting."
- "Trust anatomy load = 55%. Any test that REMOVES a trust signal (BBB, 'Since 2007', phone number) is HIGH RISK. Tests that ADD trust signals are lower risk."
- "Mobile baseline conversion is unknown — can't assess viewport-specific preservation."
- "page_context is incomplete (no semantic_map confidence < 0.7); preservation analysis has confidence ~0.65."

**Output:** `warnings_for_downstream` list + final `confidence` score (0.0-1.0).

**Quality gate:** Each warning must be ACTIONABLE — directed at a specific downstream agent's decision space. Vague warnings ("be careful") are useless; specific warnings ("DO NOT propose X without Y") are gold.

---

## When operating_constraints.baseline_conversion_rate_pct is missing

If the operator did not provide baseline conversion, my output's confidence drops to ≤0.6. I can still analyze the page structurally, but I cannot calibrate "is this working?" — only "this LOOKS like a working pattern." I flag this explicitly in `warnings_for_downstream`.

## When prior_tests_tried is provided

Read it carefully. If a prior test "Reduced form 4→3 fields, +6% in March" is in the list, that establishes:
- Form-shortening direction is validated
- Operator already harvested the obvious "form pruning" win
- Future form tests need to test the NEXT level (field ORDER, single-field vs multi-step, etc.) not repeat the obvious move

Use `prior_tests_tried` to prevent suggesting moves the operator has already executed.
