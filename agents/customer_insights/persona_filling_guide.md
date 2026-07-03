# Persona Filling Guide

## Output schema (CustomerInsightsOutput)

```json
{
  "personas": [
    {
      "name": "string — niche-specific label, NOT generic",
      "role": "primary_buyer | influencer | decision_helper | blocker",
      "age_range": "NN-NN or NN+ (e.g. '65-80', '70+')",
      "location_context": "string — geo + life stage",
      "income_band": "under_30k | 30_60k | 60_100k | 100_200k | over_200k | unknown",
      "digital_literacy": "low | medium | high",
      "primary_job": "JTBD: 'When [X], I want to [Y], so I can [Z].'",
      "pain_points": [
        {
          "label": "3-7 word label",
          "description": "concrete observable trigger; NO platitudes",
          "severity": "low | medium | high | critical",
          "frequency": "one_time | occasional | frequent | constant",
          "addressable_by_offer": true
        }
      ],
      "trust_needs": ["string", ...],
      "decision_triggers": ["string", ...],
      "objections": ["string", ...],
      "channel_behavior": "device, scroll speed, time of day"
    }
  ],
  "pain_points_aggregate": [PainPoint, ...],
  "audience_psychology_summary": "1-2 paragraphs"
}
```

## Field-by-field filling instructions

### `name`
Niche-specific label that captures who this human IS.

- ✓ "Sarasota Helen, 72, fall-risk widow"
- ✓ "Adult-child Marcus, 47, helping mom from out of state"
- ✓ "Champion Chintan, Head of Engineering, AI-acceleration mandate"
- ✗ "John, 35, marketing manager"
- ✗ "Tech-savvy millennial"

Format: `[Geo or context] [Name], [age], [defining situation]`

### `role`
- `primary_buyer` — the one whose money flows
- `influencer` — affects but doesn't decide
- `decision_helper` — does the research and recommendation (often adult child for senior care, IT champion for B2B)
- `blocker` — actively blocks the purchase (CFO, IT security, skeptical spouse)

### `age_range`
Pattern strict: `"NN-NN"` (e.g. "65-80") OR `"NN+"` (e.g. "65+"). No other format.

### `location_context`
Geo + life stage. Not just a city.
- ✓ "Sarasota retiree, owns home outright, daughter lives in Ohio"
- ✓ "Brooklyn freelance designer, just had a baby, partner works remote"
- ✗ "Florida"

### `income_band`
**Honesty test.** What does this audience really earn?

- For senior care elders: usually `under_30k` or `30_60k`
- For senior care adult-child: `60_100k` or `100k_plus`
- For debt relief / credit repair: `30_60k` or `60_100k`
- For B2B SaaS: usually `unknown` (org role matters more)
- For DTC wellness: `60_100k` (suburban middle, NOT $200k urban professional)
- For mental health telehealth: `40_60k` to `60_100k`

If unsure, default `unknown` rather than lying with `60_100k`.

### `primary_job`
JTBD format strict: `"When [situation], I want to [action], so I can [deeper outcome]."`

The deeper outcome should be **emotional or social, not functional**. The functional outcome is the symptom; the deeper outcome is the actual sale-driver.

- ✓ "When I feel unsteady stepping out of the shower in the morning, I want to install something that lets me bathe without thinking about it, so I can stay in my own house and not become my daughter's project."
- ✗ "When I need to bathe, I want a walk-in tub, so I can be safe."

### `pain_points` (2-6 items, each)

Each pain point object must have all 5 sub-fields. Critical:
- `label`: 3-7 words. Searchable.
- `description`: ONE sentence with concrete observable TRIGGER. NO platitudes.
- `severity`: How bad? Use `high` or `critical` sparingly.
- `frequency`: How often? `frequent` is the most common.
- `addressable_by_offer`: Boolean. Some pains are real but not what your product solves. Be honest.

Examples:
- ✓ "Slipped on the wet tub floor last February and caught herself on the faucet, bruising her wrist — now dreads bathing alone"
- ✗ "Concerned about safety"

### `trust_needs` (2-5 items)
What must the page demonstrate before they convert? Should match the segment's documented trust signals.

Examples for senior care:
- "Photo of a real local installer (not a stock photo) with a name and Florida license number"
- "Explicit 'no high-pressure sales' language"
- "BBB accreditation badge with score"

### `decision_triggers` (2-5 items)
What pushes them from research to action?

- ✓ "Veteran discount mention — her late husband was a veteran"
- ✓ "Free in-home assessment with no obligation"
- ✗ "Better marketing"

### `objections` (1-5 items)
SPECIFIC objections likely to kill conversion. In customer's voice.

- ✓ "I don't want some salesman in my house pressuring me"
- ✓ "We can't really afford this without dipping into emergency savings"
- ✗ "Price"

### `channel_behavior`
Device, scroll speed, time of day.

- ✓ "Desktop in the evening after dinner, slow scroll, will read full pages"
- ✓ "Mobile during commute, fast scroll, won't open videos with sound"

### `pain_points_aggregate` (≥3 items)
Top deduplicated pain points across all personas, ranked by severity × frequency × addressable. These are what the LP MUST address above the fold.

### `audience_psychology_summary`
1-2 paragraphs. Cover:
- **Dominant emotion** (fear? frustration? shame? excitement?)
- **Dominant fear** (what are they afraid of becoming or losing?)
- **Dominant unspoken hope** (what would success look like in their own words?)

Used by Voice & Message Strategist as raw material for headline angles.

## Cardinal-error checks before shipping

1. **Decision-helper for 55+ / medical / financial / housing briefs** — at least one persona has `role="decision_helper"`. Non-negotiable.
2. **No platitudes in pain descriptions** — every description has a concrete observable trigger.
3. **JTBD format dotted i's** — every primary_job follows `"When..., I want to..., so I can..."` pattern.
4. **Income honesty** — no defaulting to `60_100k` for fixed-income segments.
5. **Verbatim quote test** — for each persona, can I write a 30-word quote in their voice that includes hesitation, contradiction, or specificity? If no, the persona is fiction.
6. **Uniquely targetable test** — could a single piece of copy uniquely speak to ONLY this persona? If two personas would nod at the same copy, merge or cut.
7. **3-5 personas total** — not less, not more.
