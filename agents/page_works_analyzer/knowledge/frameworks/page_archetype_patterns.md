# Page Archetype Patterns — How Different Page Types Convert

## Why this matters

A "working" lead-capture page looks NOTHING like a "working" ecom-product page. Same baseline conversion (e.g. 5%) means very different things across archetypes. Apply the wrong mental model and you'll preserve the wrong elements.

## Archetypes covered

### `lead_capture` — single-form, single-action, low-commitment
Target action: ZIP submit, email capture, free assessment booking, demo request.

**Working signs:**
- ≤4 form fields (varies by industry)
- Single primary CTA repeated 2-3x
- Trust signals heavy above the fold (cold traffic) OR conversion-form-adjacent
- Clear next-step expectation ("we'll call you within 24 hours")
- Phone number visible for senior/regulated audiences

**Typical baseline conversion:**
- B2C lead capture: 5-25% depending on offer-quality fit
- B2B demo request: 1-5%
- Senior care zip submit: 15-30% on warm-context page
- Insurance quote: 5-15%

**Common preservation zones:**
- Form depth (after operator has tuned it)
- Trust mechanism stack (BBB, license, "since X")
- The submit-button copy if it's specific ("Get My Free Assessment" >> "Submit")

**Common change-safe zones:**
- Hero subheadline
- Below-fold benefit list ordering
- Image variants (not the hero)
- Footer trust mechanisms (less load-bearing than hero-adjacent)

---

### `ecom_product` — single product, buy-now action
Target action: add-to-cart, immediate purchase.

**Working signs:**
- Hero image dominates (product imagery is 30%+ of conversion work)
- Reviews count + star rating prominent
- Clear price + shipping cost (no surprises)
- Risk reversal (money back, free returns) above the fold
- Add-to-cart sticky on mobile

**Typical baseline conversion:**
- DTC ecom: 1.5-5% (varies wildly by category)
- High-AOV ecom ($100+): 0.5-3%
- Subscription DTC: 2-8%

**Common preservation zones:**
- Hero product image quality + composition
- Star-rating display + review count
- Money-back guarantee placement
- Above-fold product benefits

**Common change-safe zones:**
- Below-fold detail copy
- Image gallery order
- "Why buy" sections after the buy box

---

### `ecom_listing` — multi-product index/category page
Target action: click into product detail.

**Working signs:**
- Filter/sort visible on mobile
- Product cards have: image + name + price + rating
- Bestseller tags / social proof markers
- "Quick view" on hover (desktop)

**Typical baseline conversion (CTR to PDP):**
- 8-25% — much higher than purchase conversion

**Common preservation zones:**
- Card information density (over-stripping is common error)
- Filter/sort placement on mobile

---

### `content_article` — long-form content with embedded conversion
Target action: in-content CTA click, scroll-to-form, in-line form.

**Working signs:**
- High scroll depth (>60% to second-screen)
- In-content CTAs match the surrounding paragraph context
- Author / E-E-A-T signals visible (bio, photo, credentials)
- Time-on-page > 2 minutes

**Typical baseline conversion:**
- In-content CTA → form: 1-5%
- Scroll-to-form completion: 0.5-3%

**Common preservation zones:**
- Author bio / authority signals
- Embedded data / charts (often the credibility anchor)
- The first-screen hook (drives scroll-completion)

---

### `comparison_quiz` — guided question flow → personalized output
Target action: complete quiz, get recommendation, convert on output.

**Working signs:**
- Clear progress indicator
- ≤8 questions (mobile-friendly cap)
- "Skip-able" or "back" available for low-friction
- Each question feels relevant to the recommendation

**Typical baseline conversion:**
- Quiz start → completion: 50-80%
- Quiz completion → purchase: 10-25%

**Common preservation zones:**
- Question count (more = engagement signal but completion drops)
- Question SEQUENCE (early questions set up later relevance)
- Personalization payoff (the "we recommend X because you said Y" framing)

---

### `pricing_page` — comparison + commitment
Target action: select plan, start trial, contact sales.

**Working signs:**
- 3-tier (psychological sweet spot for choice)
- Most-popular badge on middle tier
- Feature checkmarks aligned, easy comparison
- FAQ below pricing (handles objections)
- Annual/monthly toggle if applicable

**Typical baseline conversion:**
- Visit → trial start: 3-15%
- Trial → paid: 5-20% (varies massively)

**Common preservation zones:**
- 3-tier structure (changing tier count = high-risk test)
- Feature emphasis hierarchy
- "Most popular" tier signal

---

## Cross-archetype anti-patterns

- **Treating all "low conversion" the same**: 1% on ecom is bad; 1% on B2B SaaS demo is fine
- **Removing "ugly" trust signals because designer wants clean look**: design preference vs conversion preference are not the same
- **Increasing form depth to "qualify" leads when sales team wants more leads**: solves wrong problem
- **Adding urgency to a category that doesn't support it** (medical, insurance): erodes trust

## How to apply this in my workflow

1. Get archetype from page_context.page_archetype (N2 classifier)
2. Look up archetype's typical baseline conversion → calibrate "is this working?" assessment
3. Find the working signs present + missing → score LIFT levers
4. Apply preservation zones rules of thumb
