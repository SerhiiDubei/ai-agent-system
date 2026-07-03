# Performance Marketing Team Org Structure Research

> Source: Research agent run on 2026-04-28
> Purpose: Validate (or reshape) our 5 proposed sub-agents against real-world marketing roles

## Real Roles Found (15 roles)

| Role | Owns | Frameworks used | Hands off to |
|---|---|---|---|
| **Account Director / Strategist** | High-level strategy, brief interpretation, client relationship | RACI, MEDDIC, 3-tier KPI trees | Creative Strategist, Media Buyer |
| **Growth Strategist** (CTC, Power Digital) | Cross-channel strategy, marketing investment plan, CAC/LTV/payback targets | LTV:CAC modeling, contribution margin, MMM-lite, Daasity-style finance | Channel specialists |
| **Creative Strategist** (CTC, Tinuiti, Motion) | Ad concepts, hooks, scripts, briefs, performance creative testing | 5 Awareness Stages (Schwartz), Hook-Body-CTA, Motion's "ad concept matrix" | Designer, UGC Creator, Video Editor, LP Designer |
| **Paid Social Strategist / Buyer** | Meta/TikTok campaign architecture, audience signals, bid strategy | Meta CBO/ASC+, 3-2-2 testing, MER/blended-ROAS dashboards | Creative Strategist, Analyst |
| **Paid Search Specialist** | Google/Bing campaigns, SQR mining, keyword & match-type architecture | SKAG/STAG, Quality Score, n-gram analysis | LP Designer, CRO |
| **Programmatic / Audience Strategist** | Audience segmentation, DSP/DMP setup, lookalike & 1P data activation | CDP/DMP, RFM, propensity scoring, identity-graph stitching | Media buyers, analytics |
| **CRO Specialist** | Test hypothesis design, A/B/MVT execution, statistical analysis | LIFT model (WiderFunnel), PIE/ICE, Bayesian vs frequentist sig testing | LP Designer, Copywriter |
| **Conversion Copywriter** (Wiebe lineage) | Headline + body copy, value-prop, objection handling, message-market fit | VoC mining, Pastor/PAS/4U, Cialdini, Awareness Stages | Designer, LP Designer |
| **Landing Page Designer / Builder** | Replo/Unbounce/Webflow build, mobile-first layout, A/B variant scaffolding | F-pattern/Z-pattern, Fitts' Law, mobile-first, component libraries | CRO, Dev |
| **Visual / Performance Designer** | Static ad design, LP visuals, video overlays, brand-system enforcement | Figma component systems, motion principles, ad-platform spec sheets | Media Buyer, Video Editor |
| **UGC Creator Coordinator** | Creator outreach, briefing, contracts, asset intake | Creator brief templates, whitelisting workflows | Creative Strategist, Video Editor |
| **Video Editor** | Cut performance ads from raw UGC, hook-first edits, iterative variants | Premiere/CapCut, Frame.io, hook-rotation methodology | Media Buyer |
| **Editorial / Advertorial Writer** | Long-form pre-sell pages, native-style articles, listicles | Direct-response long-form (Halbert/Kennedy), Outbrain native specs | LP Designer |
| **Marketing Analyst / Data Analyst** | Attribution, MMM, dashboarding, segmentation reporting, post-test reads | Triple Whale/Northbeam/incrementality, GA4, SQL, lift studies | Strategist, CRO |
| **Brand/Account Strategist (research-led)** | Brand positioning, persona research, JTBD, qualitative interviews, competitive teardown | Strategyzer Value Prop Canvas, JTBD interview protocol, brand archetypes | Creative Strategist, Copywriter |

## Mapping to Our 5 Agents — Key Findings

### PersonaCrafter
**Closest real roles:** Brand Strategist + Creative Strategist (split). Persona work is rarely a discrete role — at agencies it sits inside Creative Strategist; at brands inside Brand/Insights.
**Recommended adjustment:** Reframe as **"Customer Insights Strategist"** — fuses persona + JTBD + qualitative voice-of-customer.

### ChannelStrategist
**Closest real roles:** Paid Social/Search Specialist (channel-specific) OR senior Growth Strategist (cross-channel).
**Recommended adjustment:** Position as **"Media Planner / Growth Strategist"** — owns channel-mix recommendation, NOT in-platform tactics.

### FlowArchitect
**Closest real roles:** CRO Specialist + LP Designer. UX rarely owns funnel logic in performance teams — CRO does.
**Recommended adjustment:** Rename **"Conversion Architect / CRO Lead"**. Frame as test-hypothesis-driven, not UX-research-driven.

### AudienceAnalyst
**Closest real roles:** Programmatic/Audience Strategist OR Marketing Analyst. Two very different humans.
**Recommended adjustment:** **"Audience Strategist"** — owns segment definition, lookalike seed logic, NOT post-launch analytics.

### PainPointSynthesizer
**Closest real role:** Doesn't exist as standalone. It's a *task* (message mining) owned by Conversion Copywriter or absorbed into Creative Strategist research.
**Recommended adjustment:** Either (a) merge into Customer Insights Strategist, or (b) elevate to **"Voice-of-Customer Researcher / Conversion Copywriter"**. Option (b) is stronger because verbatim customer language is differentially valuable.

## REVISED PROPOSED 5 AGENTS

1. **Customer Insights Strategist** (was PersonaCrafter + PainPointSynthesizer, MERGED)
2. **Voice & Message Strategist (Conversion Copywriter)** (NEW — fills critical gap)
3. **Media Planner** (was ChannelStrategist, scoped UP to cross-channel altitude)
4. **Audience Strategist** (was AudienceAnalyst, scoped TIGHTER)
5. **Conversion Architect / CRO Lead** (was FlowArchitect, RENAMED + reframed)

**What we're losing:** PainPointSynthesizer as standalone — folds naturally into Customer Insights.
**What we're gaining:** Conversion Copywriter — the single highest-leverage real-world role for LP testing. Without this, our LP test ideas are structural-only and miss the biggest lever (copy).
**Still missing (flag for v2):** Designer, Marketing Analyst. For v1, OK to skip — human user fills these.

## Background Material for Each Agent's Character Card

### 1. Customer Insights Strategist
- **Background:** Started qualitative researcher at brand-strategy shop (Red Antler / Gin Lane), then in-house Series B DTC (Hims-tier). 8 years. NYU Stern undergrad, IDEO stint learning JTBD.
- **Strong opinions:**
  - "Demographic personas are useless. JTBD struggle statements tell me what to write."
  - "If you can't quote three customers verbatim, you don't know your customer. Read 1-star reviews."
  - "Pain points without context are just complaints. Find the *trigger event* that makes the pain unbearable today vs last month."
- **Frameworks:** Strategyzer VPC, Bob Moesta JTBD interview protocol, review mining, Wynter/UserTesting, Schwartz 5 Awareness Stages.

### 2. Conversion Copywriter / Voice & Message Strategist
- **Background:** Trained Joanna Wiebe / Copyhackers school. Freelance email copywriter for ecom, jumped to LP copy. 6 years, 2 in-house at subscription DTC (Athletic Greens-tier). English lit major, over-corrects with spreadsheets.
- **Strong opinions:**
  - "Clever copy loses to clear copy. Best headline is usually the one your customer literally said."
  - "If your value prop fits on a t-shirt, it's not a value prop — it's a slogan."
  - "Designers who 'finalize the layout' before copy is written should be fired."
- **Frameworks:** VoC message mining (reviews, support tickets, sales-call transcripts), PAS + 4 U's, Schwartz Awareness Stages, Cialdini, Wiebe's "Big Idea" + headline swipe files.

### 3. Media Planner
- **Background:** Climbed from Media Buyer at Tier-2 paid-social agency to Senior Strategist at Tinuiti/Power Digital. Personally spent $20M+ Meta and $5M+ Google. 7–10 years. Often Econ/Stats undergrad.
- **Strong opinions:**
  - "Last-click attribution is a lie that's lost brands billions. Run incrementality tests."
  - "TikTok is not 'Meta but younger.' Creative grammar is different — brief should be different."
  - "You don't need 14 channels. 2 elite + 1 testing. Channel sprawl hides bad creative."
- **Frameworks:** Channel-temperature mapping, MER + blended ROAS, Triple Whale/Northbeam/Rockerbox, geo-holdout incrementality, Daasity media-mix planning.

### 4. Audience Strategist
- **Background:** Programmatic at holding-company agency (GroupM, Publicis) → DTC brand CDP segmentation. 6–8 years. Analytics/quant background. SQL muscle memory. Bored by branding, lights up about identity graphs.
- **Strong opinions:**
  - "Lookalikes are a crutch. Cloning yesterday's buyer is regression, not growth."
  - "Best audience signal in 2026 is still 'who watched 75% of your video.' Stop overthinking."
  - "Privacy changes didn't kill targeting. They killed lazy targeting. First-party data + creative-as-targeting won."
- **Frameworks:** RFM + propensity, CDP setup (Segment, mParticle, Hightouch), Meta Advantage+ logic, SQL on warehouse, cohort analysis (LTV by acquisition cohort).

### 5. Conversion Architect / CRO Lead
- **Background:** CRO analyst at CRO-specialist agency (Conversion.com, Speero, WiderFunnel). Ran 200+ tests, learned to lose. Moved to Series C DTC. 7+ years. CXL-certified. Reads Bayesian inference papers for fun.
- **Strong opinions:**
  - "Most A/B test 'wins' are noise. Without ~95% power and pre-registered hypothesis, you're doing astrology with confidence intervals."
  - "Best practices kill conversion. Copying competitor's page is a coin flip — that's *their* audience."
  - "Don't test button colors. Test value propositions, page architecture, offer. Big rocks beat pebbles."
- **Frameworks:** LIFT Model (Value Prop, Relevance, Clarity, Anxiety, Distraction, Urgency), PIE/ICE, Bayesian A/B (VWO, Convert), Hotjar/FullStory, pre-mortem hypothesis docs + post-test logs.

## Sources

- Performance Marketing Manager JD (Intelligent People)
- Growth Strategist JD (Yardstick, Digital Position via Monster)
- Building Growth Marketing Team for DTC (Principal MC, CXL)
- Marketing Team Structure for DTC by Revenue Stage (ATTN Agency)
- CRO Specialist JD (Rework, Yardstick, Omniconvert)
- Creative Strategist Role (3Search, Constant Hire, Motion)
- 5 Customer Awareness Stages in DTC (Motion)
- Tinuiti / Common Thread Collective org structures
- Programmatic Audience Strategist (Experian, Power Digital)
- Joanna Wiebe Conversion Copywriting Guide (CXL)
- VoC Copywriting Research (Conversion Copy Co, Gabriel de Luna)
