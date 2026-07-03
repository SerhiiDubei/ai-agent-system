# Research: Real Persona Examples + JTBD Frameworks + Industry Patterns

> Source: Two parallel research agent runs on 2026-04-28
> Purpose: Seed knowledge files + golden_sets for Customer Insights agent system (Phase 5b)
> See `docs/research/` for full agent reports — this is the digested summary

---

## 16 real persona examples harvested (top 5 starred)

### Senior Care / Aging-in-Place
- ⭐ **Paula** — Kohler Walk-In Bath. Hip replacement → "cannot stand up in the shower" → identity anchor "age out in the house". Source: homepridebath.com
- **Carol M.** — Duncan Hearing. Couldn't hear grandkids + dementia fear convergence. Source: duncanhearing.com
- **Scott P.** — Duncan Hearing. Career-driven JTBD: "boss whispered the correction at recruiting event"
- **Melanie** — A Place for Mom. Adult daughter, father just died, looking for assisted living for newly widowed mom. *Decision-helper archetype.*

### Financial Services
- **Mary** — National Debt Relief. $22.8K debt, $1,020/mo unsustainable, "get my life back" identity-sensitive
- **Bryan** — Lemonade Homeowners (TX). First-time homeowner surprise costs. App-native segment.
- **Anonymous** — Lexington Law (CFPB-cited). Mortgage applicant, 578/600 starting score. "Trashed credit causing shame"

### B2B SaaS
- ⭐ **Chintan Turakhia** — Coinbase × Linear. AI-acceleration agenda, exec mandate, metric-anchored ("merged PRs/day")
- **Ariel/Gregory/Marc** — Zoom × Asana. Multi-stakeholder buying committee with 3 named champions
- ⭐ **James Adams** — Reed × HubSpot. "Customer service reps taking lead info by hand" → "limited visibility"

### DTC Ecom (Wellness/Subscription)
- **AG1 long-term customer** — "demanding so much of my body" → ritual replacement JTBD
- **Care/of "constant traveler"** — time zones disrupted routine, "lugging six different bottles"
- **Care/of "overwhelmed researcher"** — "shelf full of half-used vitamins" failed-prior-solution archetype

### Healthcare Consumer
- ⭐ **Megan Whitaker** — Talkspace postpartum. 8 p.m. panic attack, $200 house calls comparison, spousal push, identity threat ("unfit mother")
- **Hims composite** — male hair-loss/ED avoider. "<10% of men 20-40 comfortable raising w/ PCP"
- **BetterHelp customer** — first-time therapy at 58, rural geography trigger

---

## Top 5 cross-industry patterns

1. **Strong personas have a precise trigger event with a TIME ANCHOR** (last week / past month). Weak ones describe chronic state.
2. **Strong personas name a specific competing alternative** with price or behavior — not just "the status quo".
3. **Decision-helper isn't always who you'd guess** — Melanie's mom is user; Melanie buys. Husband can be trigger-pusher not just helper.
4. **Identity threats are louder than functional pains** — Scott didn't want to "look old"; Megan didn't want to be seen as "unfit"; Paula wanted to "age out in the house". Functional pain is symptom; identity threat is the actual sale-driver.
5. **Strong personas describe what they tried BEFORE** (failed self-managed attempt) — Care/of's "shelf full of half-used vitamins"; James's "we used basic tools and handwritten slips". Moment of admitted defeat = ad copy gold.

---

## 10 frameworks deep-dive (from agent 2)

1. **Christensen JTBD** — functional + emotional + social. Emotional usually 3-5× functional.
2. **Moesta Forces of Progress** — push + pull > anxiety + habit. 6-step interview protocol.
3. **Klement Jobs as Progress** — JTBD reframed as "progress toward better self in specific situation"
4. **Schwartz 5 Awareness Stages** — Unaware → Most Aware. Per-stage ad headline patterns documented.
5. **Sharp/Romaniuk CEPs** — 7 W's framework (When, Where, While, With whom, Why, hoW feeling, What for)
6. **Maslow → Pain Points** — physiological → safety → belonging → esteem → self-actualization marketing ladder
7. **Caregiver Burden (Zarit/Pearlin)** — niche-specific (medical, senior care)
8. **Health Belief Model** — susceptibility + severity + benefits − barriers + cues + self-efficacy
9. **Identity-Protective Cognition (Kahan)** — when "obviously-better product won't sell" — block is identity, not feature
10. **Mom Test (Fitzpatrick)** — extract truth via past behavior, never future opinion

---

## 5 industry-specific persona patterns

### Senior Care
- **Buyer = adult daughter** (48-62, $75-150k HHI). NOT the elder.
- **Triangulated decision:** daughter researches, elder consents, sibling/spouse can block
- **Trigger patterns:** hospital discharge, fall, missed medication, driving incident, spouse's death
- **The lie:** marketers assume seniors have nest eggs; reality is daughter pays
- **Trust signals:** state licensure, "bonded & insured caregivers", named care coordinator

### Financial Services
- **Buyer:** 28-55, $35-85k HHI. Mobile-first.
- **Hidden ghost:** "prior bad actor" — burned by sketchy debt-relief / payday — present in every conversation
- **Trigger patterns:** medical bill, divorce, job loss, garnishment, collections call AT WORK
- **The lie:** "irresponsible spender" trope — usually it's a medical or divorce event
- **Trust signals:** BBB A+, AFCC/IAPDA, NMLS, A.M. Best, no upfront fees

### B2B SaaS
- **Committee:** Champion + Economic Buyer + Tech/Security + End Users + Procurement (~6.8 stakeholders avg)
- **#1 deal-killer at $50k+:** InfoSec/IT
- **Champion authority lie:** champion has $5-10k expense ceiling, not real budget
- **Trust signals:** SOC 2 Type II, ICP logos, G2 Leader badge, named integrations

### DTC Ecom
- **Female-skew 65-75%** for wellness/beauty/supplements
- **Friend group chat** sells more than ads (one screenshot)
- **The lie:** "premium wellness consumer = $200k+ HHI"; reality is $60-100k suburban women prioritizing within budget
- **Trust signals:** third-party testing (NSF, USP), founder story, real customer photos w/ first names + cities

### Healthcare Consumer
- **Privacy-sensitive** uniquely — "will this show up on EOB?" is dealbreaker
- **Mental health skews 50% Problem-Aware + 20% in-denial Unaware**
- **The lie:** "self-pay $300/mo concierge user"; reality is choosing between $99/mo and not getting care at all
- **Trust signals:** HIPAA called out, no surprise billing, board certifications, clear cancellation policy

---

## 3 workflow templates

**Workflow A: 5-day sprint** (IDEO + Wynter + VPC) — for typical commercial work
**Workflow B: Indi Young Mental Models** (4-6 weeks) — gold standard for empathy depth, regulated industries
**Workflow C: HubSpot/Strategyzer Quick Persona** (2 weeks) — campaign-ready v0.5

---

## How this maps to our Customer Insights agent system

**identity.md / beliefs.md** — universal expert (drawn from research patterns, not niche-specific)
**knowledge/frameworks/** — 10 framework files
**knowledge/market_segments/** — 5 segment pattern files
**golden_sets/** — top 5+ persona examples as JSON
**workflow.md** — adapted from Workflow A (5-day sprint compressed to LLM-execution)
**persona_filling_guide.md** — schema + field-by-field instructions
**anti_patterns.md** — derived from "the lies" + cross-industry patterns

This is the source material for Phase 5b. Each section above maps to a knowledge file.
