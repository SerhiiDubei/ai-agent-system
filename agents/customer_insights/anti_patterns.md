# Anti-Patterns I Refuse to Ship

These are the cardinal sins of persona research. Each one is a fail-fast trigger.

## Persona-level anti-patterns

### 1. Demographic-only personas
**Symptom:** persona reads as `"65+ female, $40-60k household income, lives in Sun Belt"` with no trigger event, no JTBD, no specific situation.

**Fix:** add a trigger event with a time anchor + JTBD progress statement.

### 2. "Tech-savvy millennial" (or any generic-stereotype persona)
**Symptom:** persona could fit ANY niche; could be the same person with a different age label across briefs.

**Fix:** make it niche-specific. "Tech-savvy millennial" → "Brooklyn freelance designer, just had a baby, partner works remote."

### 3. Platitude pain points
**Symptom:** "Concerned about safety." "Wants peace of mind." "Values quality and convenience." "Better life."

**Fix:** rewrite with concrete observable trigger. "Concerned about safety" → "Slipped getting out of the tub last winter and caught herself on the faucet."

### 4. Single-buyer personas for multi-stakeholder decisions
**Symptom:** B2B brief has only an end-user persona, no procurement/IT blocker. Senior care brief has only the elder, no adult-child decision_helper.

**Fix:** add the decision_helper or blocker. For 55+/medical/financial briefs this is non-negotiable.

### 5. Defaulting to middle-class income
**Symptom:** every persona magically lands at `60_100k` HHI even for fixed-income niches.

**Fix:** apply the segment's income realism. Walk-in tubs / Medicare / debt relief → most personas are `under_30k` or `30_60k`. Adult-child decision-helpers can be higher.

### 6. Personas whose verbatim quote is interchangeable
**Symptom:** if you swapped Persona A's quote with Persona B's, no one would notice. The personas are the same person with different labels.

**Fix:** make each persona uniquely targetable. If two would nod at the same copy, merge or cut.

### 7. Brand-deck language instead of customer language
**Symptom:** persona quotes use phrases like "aging gracefully," "active lifestyle," "vibrant senior," "discerning consumer."

**Fix:** use customer language. "Don't want to be a burden." "Still want to live in my own house." "Don't want to be the one falling apart at 40."

### 8. Persona quotes written as testimonials
**Symptom:** quote praises the brand or product ("HomeIQ made the whole process easy"). That's a testimonial.

**Fix:** persona quote is BEFORE the purchase, in their own struggle. "I just don't want to fall again."

## Trigger-event anti-patterns

### 9. Chronic-state triggers
**Symptom:** "She has been worried about her safety for a long time."

**Fix:** anchor to an EVENT with a time stamp. "Last winter she slipped." "Two weeks ago her daughter started sending assisted-living brochures."

### 10. Inferred opinion masquerading as trigger
**Symptom:** "She values independence." That's an opinion, not a trigger.

**Fix:** what HAPPENED that revealed this value? "Her doctor suggested moving to assisted living last month — she said no immediately."

## JTBD anti-patterns

### 11. Functional-only JTBD
**Symptom:** primary_job = "When I want to bathe, I want a walk-in tub, so I can be clean."

**Fix:** add the emotional/social outcome. "When I feel unsteady stepping out of the shower, I want to install something safer, so I can stay in my own house and not become my daughter's project."

### 12. JTBD that's a wish, not a job
**Symptom:** "When I shop online, I want a great experience."

**Fix:** "When I'm comparing supplements at 11pm and getting overwhelmed by labels, I want a quiz that tells me what to pick, so I can stop wasting an hour and start sleeping better."

## Workflow anti-patterns

### 13. Skipping market_segments load
**Symptom:** persona reads from general knowledge, not segment-specific patterns. Senior care brief produces personas without decision_helper.

**Fix:** ALWAYS load `knowledge/market_segments/<segment>.md` before drafting. Read it end-to-end.

### 14. Ignoring page_context when present
**Symptom:** persona pain_points and trust_needs ignore what the actual page already shows.

**Fix:** if page_context loaded, persona's trust_needs should reference page elements ("BBB badge already present — needs to be more prominent" not "needs BBB badge").

### 15. Inventing personas from imagination instead of segment patterns
**Symptom:** persona names don't match how this segment's audience actually identifies (using "boomer" terminology for an audience that calls themselves "active retirees").

**Fix:** check segment's documented "anti-personas to avoid" — make sure you're not building one.

## Cross-industry anti-patterns

### 16. Wealth-aspirational imagery for stretched-middle audiences
**Symptom:** persona is described doing yoga in a $4M LA home for a $99/mo supplement targeting $60-100k HHI.

**Fix:** match the persona's reality, not the brand's aspiration.

### 17. "I'm not the kind of person who..." identity rejection ignored
**Symptom:** persona for therapy app describes a "depression sufferer" — ignoring that 90% of the audience identifies as "stressed" or "going through something," not "depressed."

**Fix:** apply identity-protective cognition (`identity_protective_cognition.md`). Reframe to match how the audience self-identifies.

### 18. Using competing-alternative language without naming the alternative
**Symptom:** "She compared us to other options" — vague.

**Fix:** name the alternative with a price or behavior. "Compared us to $200/session in-person therapy." "Compared us to 'just toughing it out one more month.'"
