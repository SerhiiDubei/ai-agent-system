# Voice-of-Customer Mining Protocol

## Source hierarchy by signal-to-noise

| Source | Signal quality | Why |
|---|---|---|
| 1-star reviews | ★★★★★ | Negative reviews name specific friction in customer's words |
| Sales call transcripts | ★★★★★ | Real objections + their actual hesitation language |
| Support tickets | ★★★★ | Customer's actual problem in their words |
| 5-star reviews | ★★★ | Often generic celebration ("loved it!") with low signal |
| NPS verbatims | ★★ | Performative, brand-shaped |
| Marketing surveys | ★ | Brand's questions → brand-shaped answers |
| Brand decks | ☆ | The brand's wishful thinking about customer |

## Review-mining heuristic
**Read 30 1-star reviews end-to-end before drafting any persona.** Cluster the recurring objections — those become persona objections, trust_needs, and pain_points (in that order of usefulness).

## The 4-question customer-interview protocol (Wynter / IDEO / Moesta mashup)

When real interviews aren't possible, mentally simulate plausible answers grounded in the niche, brief, and any reviews available:

1. **What were you trying to do when you found this product?**
2. **What had you tried before that didn't work?**
3. **Who else weighed in on the decision?**
4. **What almost stopped you from buying?**

## The "Mom Test" rule for plausible quotes

When reconstructing voice for a persona where no actual customer quotes exist, frame everything as **past behavior**, never future opinion:

- ✗ "I would value safety above all else."
- ✓ "I slipped getting out of the shower last winter and I haven't taken a bath since."

- ✗ "I want to be more productive at work."
- ✓ "Last Thursday's QBR prep took me 6 hours and I still missed three things my CRO asked about."

Real human voice includes:
- Hesitation ("I don't know, maybe...")
- Contradiction ("I want to be independent, but I also don't want to fall again")
- Specific concrete details (Thursday, 6 hours, three things, last winter)
- Trailing off, deflection, name-dropping ("my daughter Jenny says...")

## Anti-patterns

- Quotes that sound like taglines ("Finally, a solution that works for me!")
- Quotes that praise the product ("HomeIQ made the whole process easy") — that's a testimonial, not a persona quote
- Quotes that mention brand benefits ("Their 10-year warranty gave me peace of mind")
- Quotes in third person ("She wants safety and convenience")

## When I have access to actual VoC

If the brief includes retrieved knowledge chunks containing real reviews/quotes, **use them DIRECTLY as voice_examples**. Don't paraphrase. Verbatim is the entire point.

If the page_context contains existing on-page copy, identify which lines sound like brand-deck and which sound like real customer voice (e.g. testimonial blocks). Lift the customer voice.
