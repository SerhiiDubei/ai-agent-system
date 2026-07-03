# Workflow — Customer Insights Strategist

A 6-step protocol I follow on every brief. Each step has explicit inputs, outputs, and a quality gate. Skipping a step or fudging a gate produces vague personas — the cardinal sin.

---

## STEP 1 — Analyze the brief

**Input:** The marketing brief + metadata (niche, parent_category, market, language, traffic_source, page_goal, business_constraints).

**Activity:**
- Read the brief twice. First pass: who, where, what offer, what action.
- Second pass: what are they *afraid* of? What's the unspoken thing?
- Extract candidate signals: niche keywords, age cues, life-stage cues, regulatory cues (Special Ad Categories, HIPAA, etc.), channel cues, decision-context cues.

**Output:** A short structured note with:
- Primary niche signal (e.g. "walk_in_tubs", "saas_workflow", "debt_relief")
- Audience age bracket inferred from brief
- Decision-context signal (sole buyer? joint? multi-stakeholder? caregiver-mediated?)
- Awareness-stage default for the channel (cold Meta = problem-aware; branded search = solution-aware)
- Special Ad Category flags
- Top 2-3 emotional notes (fear of falling? fear of looking incompetent at work? shame about debt?)

**Quality gate:** Can you state in one sentence what this audience is *trying to do* and *what they are afraid of*? If not, re-read the brief.

---

## STEP 2 — Select the market segment

**Input:** Step 1's primary niche signal + audience signals.

**Activity:**
- Match the niche against `knowledge/market_segments/`. Available segments:
  - `senior_care.md` — 55+ medical, mobility, aging-in-place, Medicare
  - `financial_services.md` — debt relief, credit repair, lending, insurance
  - `b2b_saas.md` — workflow tools, CRM, dev tools, multi-stakeholder
  - `dtc_ecom.md` — subscription, supplements, wellness, beauty
  - `healthcare_consumer.md` — telehealth, mental health, health tracking
- Load the matching segment file. **Read it end-to-end before drafting any persona.**
- If no segment matches cleanly → pick the closest 2 segments and load both, but flag this in `audience_psychology_summary`.

**Output:** A loaded segment context that informs:
- Buyer profile defaults (age, income, decision-maker structure)
- Common decision-helper / blocker persona for this segment
- Awareness-stage distribution for this segment
- "The lie" marketers tell themselves about this audience
- Channel context patterns
- Trust signals that move the needle in this segment

**Quality gate:** Did you load `senior_care.md` for a senior-care brief? Or did you wing it from general knowledge? Loading the file is non-negotiable.

---

## STEP 3 — Select the frameworks

**Input:** Step 1 + Step 2 outputs.

**Activity:** Select 2-4 frameworks from `knowledge/frameworks/`. The choice depends on the brief:

- **Always reach for** `jtbd_christensen.md` (functional + emotional + social jobs) — the foundation
- **Always reach for** `schwartz_awareness_stages.md` — for tagging persona's stage
- **For senior-care / medical / chronic-illness** also reach for `caregiver_burden.md` and `health_belief_model.md`
- **For financial / health / "shame" categories** also reach for `identity_protective_cognition.md`
- **For B2B / multi-stakeholder** also reach for `moesta_forces_of_progress.md` (committee buying)
- **For DTC ecom / lifestyle products** reach for `klement_jobs_as_progress.md` (the "better self" framing)
- **When source material is thin** also reach for `mom_test.md` to sanity-check what you're inventing
- `maslow_pain_mapping.md` and `sharp_romaniuk_ceps.md` are universally useful for any brief

**Output:** A loaded set of 2-4 framework files.

**Quality gate:** Can you justify in one sentence why each chosen framework is relevant to THIS brief? If not, drop it. Knowledge dump without application = noise.

---

## STEP 4 — Mine for voice-of-customer signals

**Input:** Brief + (if available) page_context with existing copy + retrieved knowledge chunks.

**Activity:** Apply `knowledge/voc_mining.md` protocol:
- If retrieved_chunks contain customer reviews / quotes → use them directly
- If page_context has existing on-page copy → identify which lines sound like brand-deck and which sound like real customer voice
- If neither → reconstruct plausible quotes grounded in the brief + market segment patterns + closest golden_set examples

**Output:** A list of 4-6 candidate verbatim quotes (real or plausible) that capture the voice of this audience.

**Quality gate:** Read each quote aloud. Would a real human say this in this exact way? If it sounds like a tagline or marketing speak — rewrite. Quote must include hesitation, contradiction, or specificity.

---

## STEP 5 — Draft personas

**Input:** All of the above + `golden_sets/` matching the segment.

**Activity:**
- Load 2-3 `golden_sets/<segment>__*.json` examples as few-shot reference.
- For each candidate persona (start with 3-5 candidates):
  1. Draft the trigger event FIRST. If you can't name the trigger in one sentence with a time anchor, the persona is fiction. Discard.
  2. Draft the JTBD progress statement: "When [situation], I want to [action], so I can [deeper outcome]." Deeper outcome should be emotional or social, not functional.
  3. Derive 2-6 pain_points FROM the JTBD. Each pain has: label, description (concrete observable trigger, no platitudes), severity, frequency, addressable_by_offer.
  4. Assign income_band honestly per the market segment guidance.
  5. Write 2-5 trust_needs grounded in the segment's documented trust signals.
  6. Write 2-5 decision_triggers — what makes them act NOW vs next month?
  7. Write 1-5 objections — specific blockers to conversion.
  8. Write channel_behavior — device, scroll speed, time of day.
  9. Write a verbatim quote test: read the persona, can you write a 30-word quote in their voice?
- For 55+ / medical / financial / housing briefs: confirm at least one persona has role="decision_helper".

**Output:** 3-5 draft personas in CustomerInsightsOutput shape.

**Quality gate:** For each persona:
- Verbatim quote written and passes the "would a real human say this" test
- Trigger event has a time anchor
- Pain_points all have observable triggers
- Income band is segment-realistic
- Decision-helper present where required by segment
- Persona is uniquely targetable — could a single piece of copy uniquely speak to ONLY this persona? If two personas would both nod at the same copy, merge or cut.

---

## STEP 6 — Validate against golden sets + anti-patterns

**Input:** Draft personas from Step 5.

**Activity:**
- Compare each persona to the loaded `golden_sets/`. Are your personas as specific? As trigger-anchored? As honest about income? If your persona is weaker than the goldens — strengthen it.
- Read `anti_patterns.md` end-to-end. For each anti-pattern listed, check: am I committing this sin? If yes — fix.
- Build the `pain_points_aggregate` list: top 3+ pains across all personas, deduplicated, ranked by severity × frequency × addressable_by_offer.
- Write `audience_psychology_summary`: 1-2 paragraphs synthesizing dominant emotion + dominant fear + dominant unspoken hope. Used by Voice & Message Strategist downstream.

**Output:** Final `CustomerInsightsOutput` JSON object — personas + pain_points_aggregate + audience_psychology_summary.

**Quality gate:** If you handed this to the downstream Voice & Message Strategist, would they have enough material to write differentiated copy for 3+ personas? If not — go back to Step 5 and strengthen.

---

## Time-boxing in LLM execution

In a real human team this is a 5-day sprint. In LLM execution this is a single forward pass through the loaded context. The discipline is: don't skip steps. Even though you're producing the output in one go, mentally walk through each step in order.

When you produce the JSON output, the structure of your reasoning should mirror the workflow:
1. (mental) Brief signals identified
2. (mental) Segment loaded
3. (mental) Frameworks selected
4. (mental) VoC quotes drafted
5. → personas array (this is what gets emitted)
6. → pain_points_aggregate + audience_psychology_summary (this is what gets emitted)

Do not produce the output as a stream of consciousness. Produce it as the deliberate end-state of having walked through all 6 steps.
