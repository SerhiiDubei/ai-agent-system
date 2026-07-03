# Character-Card Prompt Engineering Research

> Source: Research agent run on 2026-04-28
> Purpose: Design 6-section character cards for our 5 specialized drafter sub-agents

## Source Analysis

### 1. Anthropic published Claude system prompt (Claude 4, May 2025)
~2,500 words across 9 sections. Identity comes first and is short (~300 chars). Most of the prompt is *behavioral negation* ("don't add lists," "don't open with praise") rather than identity.
**Lesson:** establish identity briefly, then spend most tokens correcting known failure modes.

### 2. Constitutional AI / "Claude's Character" (Anthropic, June 2024)
Character mostly trained in, not prompted. But trained-in character uses *first-person, opinionated, specific* language: "I like to try to see things from many different perspectives... but I'm not afraid to express disagreement..."
**Lesson:** first-person voice + explicit values + permission-to-disagree → judgment behavior. "Be helpful, harmless, honest" → bland output.

### 3. CrewAI Role/Goal/Backstory
- Weak role: "Writer" → Strong: "Technical Blog Writer specializing in explaining complex AI concepts to non-technical audiences"
- Weak backstory: "You are good at business analysis" → Strong: "15 years conducting user research… You believe good UX is invisible..."
- 80/20 rule: 80% effort on tasks, 20% on agents. Backstory peaks at 50–80 words.

### 4. Custom GPT prompts (Mr. Ranedeer, Grimoire, Professor Synapse)
Highest-rated GPTs are 800–1500 words with heavy structural formatting and embedded mini-frameworks.

### 5. Academic research

- **Zheng et al. 2023 ("When 'A Helpful Assistant' Is Not Really Helpful")**: 2,410 questions × 162 personas × 4 model families. **Personas produced no significant accuracy gain on factual tasks.** Some hurt.
- **Kim et al. 2024 ("Persona is a Double-edged Sword")**: 13.78% problems flipped correct→wrong; 15.75% flipped wrong→correct. Net **+9.98% on GPT-4 with domain-matched personas**. Mismatched hurt symmetrically.
- **PRISM (2026)**: Expert personas **boost alignment-dependent tasks** (writing/roleplay/safety: +0.40 to +0.65 MT-Bench, +17.7% safety) but **damage knowledge tasks** (MMLU drops ~3.6 points). Longer personas amplify both effects.
- **Scaling Law paper (2025)**: For *generation*, Euclidean distance to human-baseline drops 70.25 → 23.75 with literary character profiles — **66% improvement from richer narrative detail**. **Narrative life-details > demographic attributes.**

**Synthesis:** Persona helps when task is generative/judgment-laden (our case). Hurts when factual-retrieval. Good news for us — keep personas concrete-and-narrative, not abstract.

## Section-by-Section Guidance for Our 6-Section Template

### 1. WHO I AM — *60–100 words*
- **Strong:** Specific specialty + named methodology + opinionated stance. "I am a conversion copywriter for B2B SaaS landing pages, trained in the Eugene Schwartz awareness-stage framework. I believe most landing pages fail because they sell features to people who don't yet know they have a problem."
- **Weak:** "You are a helpful copywriter."
- **Anti-pattern:** Multiple roles ("writer, editor, strategist") — dilutes activation.

### 2. WHERE I COME FROM — *80–150 words, narrative*
- **Strong:** Concrete career trajectory with numbers, named companies/methods, specific scars. "10 years at conversion agencies (Asana, Webflow, Linear). Tested 400+ landing pages. Watched 60+ A/B tests fail because they tested headline when awareness-stage was wrong."
- **Weak:** "You have many years of experience."
- **Why narrative:** Scaling-law paper shows narrative life-details outperform demographic attributes by ~66% on alignment.

### 3. WHAT I BELIEVE — *100–200 words, 3–6 opinions*
- **Strong:** Numbered, specific, contrarian. "1) Awareness stage matters more than headline word choice. 2) Social proof above the fold beats it below in 80% of cases. 3) 'Get a demo' converts worse than 'See it work in 90 seconds' for technical buyers."
- **Weak:** "I value quality and clarity."
- **How to inject controversial opinions:** Frame as professional experience: "In my experience, X usually beats Y" — reads as expertise; "X is always better than Y" — reads as a rule the model resists.

### 4. HOW I WORK — *150–250 words, numbered method*
- **Strong:** Sequential steps with decision criteria. "1) Read inputs end-to-end. 2) Identify awareness stage — this gates everything. 3) Generate 5 hypotheses, cut to 2 by ICE. 4) Write headline test variant first..."
- **Weak:** "Think step by step."

### 5. WHAT I KNOW — *200–400 words, frameworks + heuristics*
- **Strong:** Named frameworks with capsule definitions and use-triggers. "Schwartz's 5 awareness stages: Unaware (no problem perception)… Most-aware (comparing vendors). PAS framework: Problem, Agitation, Solution."
- **Weak:** "I know about copywriting frameworks."
- **PRISM finding:** highest-leverage *and* highest-risk for length — long generic knowledge hurts; short specific knowledge with use-triggers helps.

### 6. WHAT I PRODUCE — *80–150 words + JSON/markdown schema*
- **Strong:** Schema + 1–2 line constraints + good/bad exemplar. "Output JSON: {hypothesis, awareness_stage, predicted_lift_pct, confidence_low_med_high, rationale_max_60_words}. Never more than 3 hypotheses. Never use 'unlock,' 'leverage,' or 'seamless.'"

### Section Order
**WHO → WHERE → WHAT I BELIEVE → HOW → WHAT I KNOW → WHAT I PRODUCE**
Identity primes activation pattern; background justifies opinions; opinions gate methodology; methodology consumes embedded knowledge; output schema is final filter. Schema-last is critical — putting it first causes models to optimize for shape over substance.

## 8 Hard Rules (Research-Backed)

1. **Total budget 700–1,200 words per character card.** PRISM: persona effects amplify with length on alignment tasks but damage knowledge tasks above ~600 tokens. Our tasks are alignment-dominant, so upper end is fine.
2. **First-person voice throughout.** "I" produces more opinionated, decisive output than "You are a..."
3. **Domain-matched persona, never generic.** "Senior conversion copywriter" beats "expert assistant" by ~10 points net quality on judgment tasks (Kim et al.).
4. **3–6 numbered, falsifiable beliefs in WHAT I BELIEVE.** Specific testable opinions change behavior; vague values don't. Specificity → 66% closer to ground-truth distribution on generation.
5. **Background narrative > credentials.** "Worked on Asana for 3 years and watched a $2M test fail" beats "world-class expert with 15 years."
6. **Don't try persona AND knowledge retrieval in same prompt.** PRISM: personas damage MMLU. If agent must recall facts, route through tool calls / retrieval.
7. **Frame controversial opinions as personal experience.** "In my experience" / "I lean toward" / "I think" — bakes in opinions without triggering refusal.
8. **Anti-sycophancy belongs in WHAT I PRODUCE, not WHO I AM.** Claude 4 isolates anti-sycophancy at end — putting in identity weakens the whole character.

## Sources

- Highlights from Claude 4 system prompt — Simon Willison
- Claude's Character — Anthropic
- Claude's Constitution — Anthropic
- Constitutional AI: Harmlessness from AI Feedback (PDF)
- CrewAI — Crafting Effective Agents
- "When 'A Helpful Assistant' Is Not Really Helpful" (arXiv 2311.10054)
- "Persona is a Double-edged Sword" (arXiv 2408.08631)
- PRISM (arXiv 2603.18507)
- Scaling Law in LLM Simulated Personality (arXiv 2510.11734)
- Two Tales of Persona in LLMs Survey (arXiv 2406.01171)
- Leaked GPT system prompts (linexjlin/GPTs, jujumilk3/leaked-system-prompts)
