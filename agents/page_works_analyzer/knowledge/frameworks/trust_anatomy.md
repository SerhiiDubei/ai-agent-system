# Trust Anatomy — Mechanism + Load Share Heuristics

## Core idea

A working page has 3-7 distinct trust mechanisms working together. Each carries a load share — an estimated % of conversion work. Sum across mechanisms approximates the page's "trust budget." For cold-traffic regulated industries, trust budget can be 50%+ of total persuasive work.

## Common trust mechanisms by category

### Authority / accreditation (~10-25% load each in regulated industries)
- BBB rating (especially A+)
- State license number prominently displayed
- AFCC / IAPDA / NMLS / NAIC etc.
- "Joint Commission accredited" / SOC 2 / HIPAA badges
- Better Business Bureau seal
- Government program acceptance (Medicare, Medicaid)

### Longevity / scale (~10-15% load)
- "Since [year]" — 10+ years gets meaningful weight
- "[N,NNN] customers served" with specific large number
- "We've helped [specific persona] for [duration]"

### Social proof (~10-25% load depending on density)
- Testimonial wall with first names + cities + photos (real ≫ stock)
- Video testimonials (heavier than text)
- Press logos ("As seen in...")
- Trustpilot / Google review counts
- Specific case-study with numeric outcome

### Risk reversal (~5-15% load)
- Money-back guarantee
- Free trial / no credit card required
- "No upfront fees" (FTC-mandated for debt relief — counts anyway)
- Cancel anytime
- 100-night trial (mattress)
- 10-year warranty

### Personal connection (~5-15% load)
- Founder photo + story
- "Talk to a real human" CTA + named coordinator
- Local installer photo with name and license
- Phone number prominently visible (esp. for senior audiences)

### Specificity premium (~5-10% load — multiplier across all mechanisms)
- Specific numbers ("4,500 Florida seniors") beats generic ("thousands of customers")
- Specific timeframes ("for 18 years") beats vague ("for years")
- Specific names ("Margaret, 74, Sarasota") beats anonymous

## Load share estimation rules

When estimating load_share %, use these heuristics:

1. **Above-the-fold mechanisms** carry 1.5-2× the load of below-the-fold equivalents
2. **First-seen-after-headline** mechanism is often the biggest single-element contributor
3. **Specific > generic** — apply ~1.3× multiplier when mechanism is specific
4. **Channel-appropriate** carries more weight (cold Meta needs more trust; branded search needs less)
5. **Stack effects**: 4 weak signals can outperform 1 strong signal in cold-traffic contexts

## Anti-patterns I've seen

### "Modernization" that destroyed trust
- Removed BBB badge for design cleanliness → conversion -8%
- Replaced specific testimonial wall with abstract "100,000+ happy customers" → conversion -12%
- Hid phone number behind "Contact us" link → conversion -5% on senior audience

### Misjudged load shares
- Assumed founder-photo was decorative → it was 18% of trust load on health DTC
- Removed "Since 1997" because "modern feel" → ~10% drop

### Channel mismatch
- Heavy trust signaling on a branded-search LP → no harm but no lift; trust budget was already spent on the brand
- Low trust signaling on cold Meta → high bounce, customers needed more reassurance

## When applying this framework

Estimate load shares to TWO decimal places at first, then round to 5%-multiples for the final output. The estimate has ±5% uncertainty regardless. The point is RELATIVE ordering — which mechanism is doing the most work — not absolute precision.

## Source

Synthesized from WiderFunnel LIFT, Cialdini's six principles, Eugene Schwartz on "credibility belt", and 8 years of personal CRO audits.
