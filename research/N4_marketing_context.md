# Node N4 — Marketing Context Generator Research

> Research scope: brief-to-personas drafting node for the standalone Python multi-agent
> system (FastAPI + LangGraph + Pydantic AI + pgvector + OpenRouter + Obsidian).
> Generates 3-5 personas, pain points, user_flow, audience_profile, channel_profile from
> a 1-paragraph brief. Validated as Pydantic models, exported to Obsidian markdown,
> persisted in the `marketing_contexts` Postgres table (V9 migration).
> Already decided: AI-assisted draft + human approve (Q-MARKETING-CTX = B), Pydantic AI
> for structured output, English runtime, schema multi-locale ready.
> Date: 2026-04-27.

---

## TL;DR

1. **Build, don't buy.** None of the off-the-shelf persona generators (Userdoc, Delve AI,
   UXPressia, FounderPal, Mosai, Personadeck) match the requirements: niche-specific
   patterns rooted in our Obsidian vault, JSONB schema for persona/pain_point/user_flow
   that downstream agents consume, channel_profile field tied to traffic source, and
   versioned linkage to a `client_project_id`. Best of them (Delve AI, Mosai) are SaaS
   black boxes; cheap ones (FounderPal, UserPersona.dev) are single-shot toys.
2. **Pydantic AI is the right substrate.** Native structured output via `output_type`,
   automatic `ModelRetry` on validation failure, system-prompt + dynamic-prompt split,
   and `pydantic_graph` under the hood for multi-step flows. Use Tool Output mode for
   models that support function calling (most OpenRouter routes); fall back to Prompted
   Output for cheaper/older models.
3. **Multi-stage beats single-shot for persona quality.** Research (PersonaTwin,
   DEEPER, Orbit Media's 5-prompt method) consistently shows 2-3 stage flows
   (extract → draft → critique/validate) outperform one-shot prompts on specificity
   and consistency. Plan for 3 sub-agents: brief_parser → persona_drafter →
   sanity_judge.
4. **Ground every persona in retrieved patterns.** The single biggest cause of generic
   "John, 35, marketing manager" outputs is unprompted generation. Inject 3-5 retrieved
   knowledge_chunks (filtered by niche + market + traffic_source) into the drafter
   prompt. The Obsidian-seeded `02_Research/<niche>/personas.md` files are the anchors.
5. **Use JTBD-infused personas, not demographic blobs.** For our home-improvement /
   dating audiences, demographics matter (especially age for senior demos), but each
   persona should carry an explicit `primary_job` statement, `decision_triggers`, and
   `trust_needs` — these are what downstream Hypothesis Generator and Critic agents
   actually consume.
6. **Channel context is a first-class field.** Meta vs Google Search vs TikTok vs
   Snapchat shape the entire user mindset (push interrupt vs pull intent vs entertainment
   scroll vs Gen Z visual). Encode `channel_profile` as a discriminated union per channel,
   not a free-text blob.
7. **LLM-as-judge sanity check is cheap and worth it.** Run a second smaller model
   (gpt-4o-mini or claude-haiku) over the drafter output with a checklist
   ("does age fit pain points? does trust_need fit channel? are there 3-5 personas?
   are pain_points concrete and not platitudes?"). Reject + retry up to 2x before
   surfacing to Obsidian for human review.

---

## Top 5 existing solutions

### 1. Delve AI — Persona / Live Persona / Digital Twin
- **What it does:** Connects to GA4, CRM, social, plus 40+ public data sources.
  Auto-segments traffic into personas. "Digital Twin" lets you chat with a persona
  ("what objection would stop you from converting?").
- **What to learn:** Data-first grounding (avoids the generic-persona trap by
  starting from real cohorts). Updateable Live Persona model is a useful pattern
  for our "persona update workflow" question.
- **Why we don't buy:** Closed SaaS, no JSONB export schema we control, no per-niche
  knowledge injection from our Obsidian patterns, can't link to `client_project_id`,
  and pricing scales per workspace seat. Also requires a live data source — we
  cold-start without one.
- **Pattern to copy:** "ask the persona a question" debug UX. Worth adding to
  Obsidian markdown export ("If asked X, this persona would say Y").

### 2. Mosai (mosai.eu) — AI Persona Orchestration Platform
- **What it does:** Imports LinkedIn HTML, Big-Five personality scoring, simulated
  conversations against persona, journey mapping, content generation, all from one
  vault (browser-local IndexedDB).
- **What to learn:** The "validation by simulated conversation" loop is essentially
  LLM-as-judge in a UI wrapper. Big-Five trait scoring as a structured field is a
  nice-to-have for our `audience_profile`.
- **Why we don't buy:** Optimized for B2B SaaS personas (LinkedIn import). Useless
  for 65+ Florida walk-in-tub homeowners — they have no LinkedIn footprint. No
  channel-context modelling.
- **Pattern to copy:** Personality-trait field as part of persona schema (optional,
  Big-Five subset).

### 3. Userdoc (userdoc.fyi) — Requirements + Personas for product teams
- **Pricing:** $19-25/seat/mo, 14-day trial.
- **What it does:** Wizard mode + "sparkle" auto-generate. Integrates with Jira,
  Asana, GitHub. Persona is one document type alongside user stories and journeys.
- **What to learn:** Wizard approach (interactive Q&A to refine) is exactly the
  "persona update workflow" pattern we need. Frontmatter-style structured doc model
  matches our Obsidian export format.
- **Why we don't buy:** Locked into their data model; export is a doc, not the JSONB
  shape downstream agents need. No niche-specific seed knowledge for home-improvement
  or dating.
- **Pattern to copy:** Interactive wizard mode for the human-approve step. After
  initial draft, Obsidian note can include a checklist of "things you might want to
  refine" — ties to N4's editing-via-Obsidian flow.

### 4. UXPressia — Online Persona Builder (with AI module)
- **What it does:** Template library, journey maps, multi-persona projects.
  AI module generates from a brief.
- **What to learn:** Their template library has 10+ industry templates (incl. real
  estate, SaaS, healthcare). A reminder that **niche templates as starting points
  are valuable** even when AI-generated, for human reviewers' anchoring.
- **Why we don't buy:** Visual-doc-first; not API-friendly for our agent pipeline.
  No structured JSONB export for downstream consumption.
- **Pattern to copy:** Persona "card" visual format for the Obsidian markdown export.

### 5. FounderPal / UserPersona.dev / Inodash / Personadeck — Free single-shot
- **What they do:** Brief in → one or two personas out. Fully unstructured prose.
- **What to learn:** They are a baseline for "what NOT to ship". Output is exactly
  the "John, 35, marketing manager" trap. No grounding, no channel, no validation.
- **Why we don't buy:** Self-evident.
- **Pattern to copy:** Simplicity of the input UX (one paragraph + niche dropdown).

**Honorable mention — not a tool, but a research framework:** Emporia Research
and NewtonX run live persona research with verified respondents. Their methodology
(multi-stage qualitative + quantitative, decision-criteria mapping) informs how we
think about persona schema fields, even though we are not running surveys.

### Build vs buy verdict

**Build.** Three blocking reasons:
- **Schema ownership.** Our `marketing_contexts.personas` JSONB feeds the Hypothesis
  Generator, Critic, and KnowledgeETL agents. We need a stable Pydantic schema, not
  a SaaS export.
- **Niche knowledge integration.** The whole point of the system is using accumulated
  Obsidian patterns. No SaaS lets us inject `02_Research/home_improvement/walk_in_tub/personas.md`
  into the prompt context.
- **Cost discipline.** Marketing context drafting is ~$0.001-0.01 per draft on
  gpt-4o-mini. Any SaaS at $20+/seat/mo is wildly more expensive at our volume.

**Reuse, don't reinvent:** Pydantic AI for the agent layer, Pydantic v2 for schemas,
pgvector for retrieval, Jinja2 for prompt templates. ~300 LoC for the whole node.

---

## Code references worth studying

- **Pydantic AI agent tutorial repo (abdallah-ali-abdallah/pydantic-ai-agents-tutorial):**
  step-by-step examples with local models and Ollama; matches our model-agnostic
  OpenRouter approach. Good for hierarchical output examples.
- **Pydantic AI multi-agent applications doc** (`ai.pydantic.dev/multi-agent-applications/`):
  agent-delegation pattern (Triage → Specialist) is the template for our
  brief_parser → persona_drafter → sanity_judge flow.
- **Pydantic AI output API** (`ai.pydantic.dev/api/output/` and `/output/`): three
  modes (Tool Output, Native Output, Prompted Output). Tool Output is default for
  function-calling models; switch to Prompted Output for OpenRouter routes that don't
  reliably support tools.
- **pydantic-ai-toolsets** (`pypi.org/project/pydantic-ai-toolsets`): includes a
  Multi-Persona Debate toolset. We are not running debates between personas, but the
  pattern (one shared scratchpad, distinct system prompts per role) maps cleanly onto
  our drafter+judge two-step.
- **PersonaTwin (arXiv 2508.10906):** two-stage construct + iterative refine
  framework. Useful for the "persona update workflow" question — Stage 2 takes
  conversation/feedback and updates the persona without losing detail.
- **DEEPER paper (arXiv 2502.11078):** directed persona refinement using
  discrepancy-based rewards. Theoretical underpinning for our "user adds new info,
  AI merges" loop. The "Previous Preservation, Current Reflection, Future Advancement"
  decomposition is a useful prompt scaffold.
- **PersonaDB (arXiv 2402.11060):** collaborative-data refinement via persona JOIN.
  Relevant if we ever want to merge personas across niches (e.g., walk-in-tub buyer
  and stair-lift buyer share traits).

---

## Production case studies

True production case studies for AI-generated marketing personas in lead-gen funnels
are sparse — most published material is either (a) tool marketing, or (b) product-team
UX research personas, not paid-media targeting personas. What is documented:

- **American Family Insurance "Persona Marketing at Scale"** (Conductor): demonstrates
  per-persona content variants tied to ad targeting. Confirms the pattern
  (persona → channel-aware content), uses humans not AI, but is the closest
  analog to our pipeline shape.
- **Senior living Meta-ads case studies** (Mannix Marketing, Sage Age,
  digitalseniority.com): consistently report two persona segments — the senior
  themselves (45% of 65+ are on Facebook) AND the adult child researching for
  parent. **This dual-persona pattern is critical for our walk-in-tub example
  brief and any 65+ niche.** The system prompt should explicitly call this out.
- **Digiday (April 2026): "AI personas promise speed, but safeguards are needed."**
  Documents real failure modes: AI personas confidently asserting purchase
  behaviors that don't exist, leading marketing teams astray. Argues for human
  review + grounded data — exactly what Q-MARKETING-CTX = B already mandates.
- **Mnemonic.ai blog "Comparing AI Buyer Personas":** quantifies the gap between
  public-LLM personas and survey-grounded personas. Quote: *"Public LLMs can generate
  buyer personas that sound convincing at first glance, but they are not built to
  uncover real behavioral truths."* Reinforces the need for retrieval grounding.

---

## Concrete patterns to copy

### Complete Pydantic schema for MarketingContext

```python
# ai_sidecar/src/ai_sidecar/marketing/schemas.py
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, model_validator


# --- Enums and shared types ----------------------------------------------

class TrafficSource(str, Enum):
    META = "meta"          # Facebook + Instagram, push interrupt
    GOOGLE_SEARCH = "google_search"  # pull intent
    GOOGLE_DISPLAY = "google_display"
    TIKTOK = "tiktok"      # entertainment scroll
    SNAPCHAT = "snapchat"  # Gen Z visual
    YOUTUBE = "youtube"
    EMAIL = "email"
    ORGANIC = "organic"


class PageGoal(str, Enum):
    ZIP_SUBMIT = "zip_submit"
    PHONE_CALL = "phone_call"
    LEAD_FORM = "lead_form"
    QUIZ_COMPLETE = "quiz_complete"
    BOOK_DEMO = "book_demo"
    SIGNUP = "signup"


class DigitalLiteracy(str, Enum):
    LOW = "low"        # senior, low-income, rural
    MEDIUM = "medium"
    HIGH = "high"      # young, urban, professional


class IncomeBand(str, Enum):
    UNDER_30K = "under_30k"
    K30_60 = "30_60k"
    K60_100 = "60_100k"
    K100_200 = "100_200k"
    OVER_200K = "over_200k"
    UNKNOWN = "unknown"


# --- Pain points (typed, not free-text) ----------------------------------

class PainPoint(BaseModel):
    """A concrete, observable pain. Avoid platitudes ('wants better life')."""
    label: str = Field(..., description="Short label, 3-7 words")
    description: str = Field(
        ..., description="One-sentence concrete pain, with trigger context"
    )
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    frequency: Literal["one_time", "occasional", "frequent", "constant"] = "occasional"
    addressable_by_offer: bool = Field(
        True, description="Does the offer plausibly solve this pain?"
    )

    @model_validator(mode="after")
    def reject_platitudes(self):
        platitudes = ["better life", "save money", "be happy", "more freedom"]
        if any(p in self.description.lower() for p in platitudes):
            raise ValueError(
                f"Pain description '{self.description}' is a platitude — "
                "rewrite to a concrete observable pain with a trigger."
            )
        return self


# --- Channel profile: discriminated union per channel --------------------

class MetaChannelProfile(BaseModel):
    channel: Literal["meta"] = "meta"
    primary_placement: Literal["feed", "stories", "reels", "marketplace"]
    typical_mindset: str = Field(
        ..., description="Push-interrupt context. What were they doing before the ad?"
    )
    creative_format_pref: list[Literal[
        "static_image", "carousel", "video_15s", "video_30s", "ugc_style"
    ]]
    age_targeting_constraints: str | None = Field(
        None,
        description="Note Special Ad Categories (housing, credit, employment) "
                    "that block age/zip targeting"
    )


class GoogleSearchChannelProfile(BaseModel):
    channel: Literal["google_search"] = "google_search"
    intent_level: Literal["informational", "commercial", "transactional"]
    typical_query_examples: list[str] = Field(..., min_length=2, max_length=8)
    competitor_density: Literal["low", "medium", "high", "saturated"]


class TikTokChannelProfile(BaseModel):
    channel: Literal["tiktok"] = "tiktok"
    typical_mindset: str
    age_skew: Literal["under_25", "25_34", "mixed"]
    hook_window_seconds: int = Field(3, ge=1, le=10)


class SnapchatChannelProfile(BaseModel):
    channel: Literal["snapchat"] = "snapchat"
    age_skew: Literal["under_25", "25_34"]
    typical_mindset: str


ChannelProfile = Annotated[
    Union[
        MetaChannelProfile,
        GoogleSearchChannelProfile,
        TikTokChannelProfile,
        SnapchatChannelProfile,
    ],
    Field(discriminator="channel"),
]


# --- Persona -------------------------------------------------------------

class Persona(BaseModel):
    """One persona among 3-5. Must include JTBD primary_job."""
    name: str = Field(
        ...,
        description="Memorable label, e.g. 'Florida Helen, 72, fall-risk widow'. "
                    "NOT 'John, 35, marketing manager'."
    )
    role: Literal["primary_buyer", "influencer", "decision_helper", "blocker"]
    age_range: str = Field(..., pattern=r"^\d{2}-\d{2,3}$|^\d{2}\+$")
    location_context: str = Field(
        ..., description="Geo + life stage, e.g. 'Florida retiree, owns home outright'"
    )
    income_band: IncomeBand
    digital_literacy: DigitalLiteracy

    primary_job: str = Field(
        ...,
        description="JTBD statement: 'When ___, I want ___, so I can ___'"
    )
    pain_points: list[PainPoint] = Field(..., min_length=2, max_length=6)
    trust_needs: list[str] = Field(
        ..., min_length=2, max_length=5,
        description="What must the page demonstrate before they convert? "
                    "e.g. 'BBB rating', 'local installer photo', 'no upfront price hidden'"
    )
    decision_triggers: list[str] = Field(
        ..., min_length=2, max_length=5,
        description="What pushes them from research to action?"
    )
    objections: list[str] = Field(
        ..., min_length=1, max_length=5,
        description="Specific objections likely to kill conversion"
    )
    channel_behavior: str = Field(
        ...,
        description="How they interact with the page: scroll speed, font needs, "
                    "device, time-of-day, return-visit pattern"
    )

    @model_validator(mode="after")
    def reject_generic_name(self):
        generic = ["john", "jane", "alex", "sam", "chris"]
        first_word = self.name.split(",")[0].strip().lower()
        if first_word in generic and "marketing manager" in self.name.lower():
            raise ValueError(
                f"Persona name '{self.name}' is the canonical generic-persona "
                "anti-pattern. Use a niche-specific memorable label."
            )
        return self

    @model_validator(mode="after")
    def age_consistency_with_digital_literacy(self):
        # Soft heuristic — generally 65+ should not be 'high' digital literacy
        # without a specific reason in location_context
        if self.age_range.endswith("+"):
            try:
                base = int(self.age_range[:-1])
            except ValueError:
                return self
        else:
            base = int(self.age_range.split("-")[0])
        if base >= 65 and self.digital_literacy == DigitalLiteracy.HIGH:
            # not a hard error, but flag for sanity_judge
            pass
        return self


# --- User flow -----------------------------------------------------------

class UserFlowStage(BaseModel):
    stage: Literal[
        "awareness", "consideration", "evaluation", "intent", "action", "post_action"
    ]
    description: str
    typical_duration: str = Field(..., description="e.g. '5 sec', '2 days', '3 weeks'")
    user_question: str = Field(..., description="The question in their head at this stage")
    page_must_answer: str


class UserFlow(BaseModel):
    stages: list[UserFlowStage] = Field(..., min_length=3, max_length=7)
    primary_friction_point: str
    drop_off_hypothesis: str = Field(
        ..., description="Where do most users drop off and why?"
    )


# --- Audience profile ----------------------------------------------------

class AudienceProfile(BaseModel):
    """Aggregate description across personas — 'who is this funnel really for?'"""
    primary_persona_name: str = Field(..., description="Must match one Persona.name")
    secondary_persona_names: list[str] = Field(default_factory=list)
    estimated_primary_share: float = Field(
        ..., ge=0.0, le=1.0,
        description="Estimated share of the funnel that is the primary persona, 0-1"
    )
    market: str = Field(..., description="ISO country code or region, e.g. 'US-FL'")
    language: str = Field(..., pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    total_addressable_population_note: str | None = None


# --- Top-level container -------------------------------------------------

class MarketingContext(BaseModel):
    """One MarketingContext per client_project. Versioned."""
    schema_version: int = 1
    client_project_id: int
    niche: str
    parent_category: str
    market: str
    language: str
    traffic_source_primary: TrafficSource
    page_goal: PageGoal
    primary_metric: str
    guardrail_metrics: list[str] = Field(default_factory=list)
    business_constraints: str | None = None

    personas: list[Persona] = Field(..., min_length=3, max_length=5)
    pain_points_aggregate: list[PainPoint] = Field(..., min_length=3)
    user_flow: UserFlow
    audience_profile: AudienceProfile
    channel_profile: ChannelProfile

    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source_brief: str
    grounding_chunks_used: list[str] = Field(
        default_factory=list,
        description="Obsidian source_paths injected into the drafter prompt"
    )

    @model_validator(mode="after")
    def primary_persona_exists(self):
        names = {p.name for p in self.personas}
        if self.audience_profile.primary_persona_name not in names:
            raise ValueError(
                f"audience_profile.primary_persona_name "
                f"'{self.audience_profile.primary_persona_name}' "
                f"is not in personas {sorted(names)}"
            )
        return self

    @model_validator(mode="after")
    def channel_profile_matches_traffic_source(self):
        expected = self.traffic_source_primary.value
        actual = self.channel_profile.channel
        if expected != actual:
            raise ValueError(
                f"channel_profile.channel '{actual}' does not match "
                f"traffic_source_primary '{expected}'"
            )
        return self
```

### Pydantic AI agent definition with system prompt

```python
# ai_sidecar/src/ai_sidecar/marketing/persona_drafter.py
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from dataclasses import dataclass

from .schemas import MarketingContext
from ..knowledge.retrieval import retrieve_chunks  # pgvector + filters


@dataclass
class DrafterDeps:
    """Dependencies injected at runtime — keeps the agent stateless and testable."""
    niche: str
    parent_category: str
    market: str
    traffic_source_primary: str
    page_goal: str
    client_project_id: int


SYSTEM_PROMPT = """\
You are a senior performance-marketing strategist drafting Marketing Context for
a paid-traffic landing-page A/B test program.

Your output must conform exactly to the MarketingContext Pydantic schema.

Hard rules:

1. Generate 3-5 distinct personas. Never produce generic templates like
   "John, 35, marketing manager". Each name must be a memorable label tied to a
   concrete life situation (e.g. "Florida Helen, 72, fall-risk widow",
   "Adult-child Marcus, 47, helping mom from out of state").

2. For senior demographics (55+) ALWAYS include both the senior themselves AND
   a "decision_helper" persona — typically an adult child or spouse. This is the
   documented dual-persona pattern for senior-living, walk-in-tub, hearing aid,
   medical alert verticals. Skipping the helper persona is a cardinal error.

3. Pain points must be concrete and observable, with a trigger. NO platitudes
   like "wants a better life" or "wants to save money". A correct pain:
   "Slipped getting out of tub last winter; afraid it will happen again
   without anyone home". A wrong pain: "Concerned about safety".

4. Each persona's primary_job must be a JTBD statement in the form:
   "When ___, I want to ___, so I can ___."

5. Channel profile must reflect the traffic source's actual mechanics:
   - meta: push interrupt; user was scrolling, not searching. Hook in 2 sec.
     Note Special Ad Categories (housing, credit, employment) which block
     age/zip targeting in the US.
   - google_search: pull intent. User typed a specific query. Match the query
     intent immediately above the fold.
   - tiktok: entertainment scroll. Hook in <3 sec, vertical video native, no
     polished corporate aesthetic.
   - snapchat: under-25 skew, ephemeral feel.

6. Trust needs must be channel-appropriate. Meta + 65+ audience needs explicit
   credibility signals (BBB, local installer photo, "no high-pressure sales")
   because the user did not seek you out.

7. Use the retrieved knowledge_chunks (provided in <retrieved_context>) as
   anchors. If a chunk says "walk-in tub buyers want clear pricing not
   call-for-quote", reflect that in trust_needs. If you have no chunks for
   this niche, say so in the source_brief commentary and produce a more
   conservative draft.

8. Income band: be honest. Walk-in tub buyers in 65+ Florida are often
   fixed-income retirees (under_30k or 30_60k), not affluent. Generic AI
   tools default everyone to 60_100k — do not.

9. The audience_profile.primary_persona_name MUST match the name of one of
   the personas you produce.

10. The channel_profile.channel MUST equal traffic_source_primary.

If you cannot satisfy a constraint with the brief alone, produce your best
draft and add a note in source_brief explaining what you assumed.
"""


drafter_agent = Agent[DrafterDeps, MarketingContext](
    model=OpenAIModel("openai/gpt-4o-mini"),  # OpenRouter route
    deps_type=DrafterDeps,
    output_type=MarketingContext,
    system_prompt=SYSTEM_PROMPT,
    retries=2,  # automatic ModelRetry on validation failure
)


@drafter_agent.system_prompt
async def inject_grounding(ctx: RunContext[DrafterDeps]) -> str:
    """Dynamic system prompt — RAG inject of niche patterns and seed personas."""
    chunks = await retrieve_chunks(
        niche=ctx.deps.niche,
        parent_category=ctx.deps.parent_category,
        market=ctx.deps.market,
        traffic_source=ctx.deps.traffic_source_primary,
        usable_by_agent="marketing_context.persona_draft",
        status="approved",
        top_k=5,
    )
    if not chunks:
        return (
            "<retrieved_context>\nNo prior knowledge found for this niche. "
            "Produce a conservative draft and flag assumptions.\n"
            "</retrieved_context>"
        )
    body = "\n\n---\n\n".join(
        f"Source: {c.source_path}\nConfidence: {c.confidence}\n{c.content}"
        for c in chunks
    )
    return f"<retrieved_context>\n{body}\n</retrieved_context>"
```

### Brief-to-personas prompt template (user-message side)

```python
# ai_sidecar/src/ai_sidecar/marketing/prompts.py
from jinja2 import Template

BRIEF_TO_PERSONAS_USER_PROMPT = Template("""\
Project brief:
\"\"\"
{{ brief }}
\"\"\"

Project metadata:
- niche: {{ niche }}
- parent_category: {{ parent_category }}
- market: {{ market }}
- language: {{ language }}
- traffic_source_primary: {{ traffic_source_primary }}
- page_goal: {{ page_goal }}
- primary_metric: {{ primary_metric }}
{% if business_constraints %}- business_constraints: {{ business_constraints }}{% endif %}

Task: produce a complete MarketingContext object.

Reasoning checklist (think step by step before producing the final object):
1. Parse the brief: extract who, where, what offer, what action.
2. Identify primary buyer(s). For senior verticals also identify the adult-child
   helper.
3. Identify income band realistically from the brief context (do not default
   to middle-class).
4. For each persona, draft the JTBD statement first, then derive
   pain_points, trust_needs, decision_triggers, objections from the JTBD.
5. Select user_flow stages appropriate to the offer commitment level
   (zip_submit = short flow; book_demo = longer flow).
6. Channel_profile: pick the discriminator matching traffic_source_primary,
   then fill the channel-specific fields with actual mechanics, not generic
   marketing language.
7. Final consistency check before output:
   - audience_profile.primary_persona_name is in personas
   - channel_profile.channel == traffic_source_primary
   - 3-5 personas
   - all pain_points are concrete (no platitudes)
""")
```

### Validation logic — LLM-as-judge sanity check

```python
# ai_sidecar/src/ai_sidecar/marketing/sanity_judge.py
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from .schemas import MarketingContext


class SanityVerdict(BaseModel):
    pass_: bool = Field(..., alias="pass")
    issues: list[str] = Field(
        default_factory=list,
        description="Concrete issues found. Empty list means pass."
    )
    suggested_fixes: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


JUDGE_PROMPT = """\
You are a critical reviewer of AI-drafted Marketing Contexts. Your job is to
flag inconsistencies, generic personas, and channel mismatches BEFORE the draft
goes to a human marketer for approval.

Check this MarketingContext against ALL of these criteria:

A. Persona quality
   - Are persona names memorable and niche-specific (not "John, 35,
     marketing manager")?
   - Are 3-5 personas present?
   - For 55+ niches: is there both a senior persona AND a decision_helper
     (adult child / spouse)?
   - Do age ranges fit the niche (e.g. walk-in tub buyer should not be 25)?

B. Logical consistency
   - Does each persona's age fit their pain_points? (a 30-year-old should not
     fear "falling in tub due to age")
   - Does income_band fit location_context? (Florida retiree on Social Security
     is unlikely to be over_200k)
   - Does digital_literacy fit age + income? (65+, low income, rural → low)

C. Pain point quality
   - Are pain_points concrete with triggers? Reject platitudes like
     "wants better life", "save money", "be happy".
   - Does each pain plausibly relate to the offer?

D. Channel fit
   - Does channel_profile.channel match traffic_source_primary?
   - Are trust_needs appropriate for the channel? (Meta = high credibility
     burden; Google Search = match query intent)
   - Are decision_triggers realistic for the channel?

E. JTBD
   - Is each primary_job a real JTBD statement (When ___, I want ___, so I can ___)?

F. Schema completeness
   - audience_profile.primary_persona_name is in personas
   - All required fields filled with substantive content (not "TBD")

Return verdict. If ANY critical issue (generic personas, missing dual-persona
for 55+, channel mismatch, platitude pain points), set pass=false.
"""


judge_agent = Agent[None, SanityVerdict](
    model=OpenAIModel("openai/gpt-4o-mini"),
    output_type=SanityVerdict,
    system_prompt=JUDGE_PROMPT,
)


async def judge(ctx: MarketingContext) -> SanityVerdict:
    user_msg = f"MarketingContext to review:\n{ctx.model_dump_json(indent=2)}"
    result = await judge_agent.run(user_msg)
    return result.output
```

### Pipeline orchestration

```python
# ai_sidecar/src/ai_sidecar/marketing/pipeline.py
from .persona_drafter import drafter_agent, DrafterDeps
from .sanity_judge import judge
from .schemas import MarketingContext
from .prompts import BRIEF_TO_PERSONAS_USER_PROMPT


async def draft_marketing_context(
    brief: str,
    *,
    niche: str,
    parent_category: str,
    market: str,
    language: str,
    traffic_source_primary: str,
    page_goal: str,
    primary_metric: str,
    client_project_id: int,
    business_constraints: str | None = None,
    max_judge_retries: int = 2,
) -> tuple[MarketingContext, list]:
    """Draft → judge → optional retry → return (context, judge_history)."""
    deps = DrafterDeps(
        niche=niche,
        parent_category=parent_category,
        market=market,
        traffic_source_primary=traffic_source_primary,
        page_goal=page_goal,
        client_project_id=client_project_id,
    )
    user_prompt = BRIEF_TO_PERSONAS_USER_PROMPT.render(
        brief=brief,
        niche=niche,
        parent_category=parent_category,
        market=market,
        language=language,
        traffic_source_primary=traffic_source_primary,
        page_goal=page_goal,
        primary_metric=primary_metric,
        business_constraints=business_constraints,
    )

    judge_history = []
    for attempt in range(max_judge_retries + 1):
        run = await drafter_agent.run(user_prompt, deps=deps)
        ctx = run.output
        ctx.client_project_id = client_project_id
        ctx.source_brief = brief
        verdict = await judge(ctx)
        judge_history.append(verdict)
        if verdict.pass_ or attempt == max_judge_retries:
            return ctx, judge_history
        # Append fix instructions to prompt for retry
        user_prompt += (
            f"\n\nPrevious draft rejected by reviewer. Issues: "
            f"{verdict.issues}. Suggested fixes: {verdict.suggested_fixes}. "
            "Produce a corrected MarketingContext."
        )
    return ctx, judge_history
```

### Persona update workflow (merge new info without losing detail)

```python
# ai_sidecar/src/ai_sidecar/marketing/updater.py
"""When a user shares new audience info on an existing project, merge it into
the existing MarketingContext without destroying detail. Inspired by DEEPER
(Previous Preservation, Current Reflection, Future Advancement)."""

UPDATER_PROMPT = """\
You are updating an existing MarketingContext with new information from the user.

Three goals (in order of priority):
1. PRESERVE: keep all existing detail unless explicitly contradicted.
2. INTEGRATE: merge new info into the right field. New pain points get appended
   (deduplicated). New persona observations refine existing personas; only add
   a new persona if the new info describes a clearly distinct segment.
3. RESOLVE CONFLICTS: if new info contradicts old, prefer new and add a note in
   source_brief documenting the change.

Do NOT regenerate from scratch. Do NOT drop fields not mentioned in the update.

Existing MarketingContext:
{existing_json}

New info from user:
{new_info}

Output: full updated MarketingContext. Increment version by 1.
"""
```

---

## Anti-patterns

1. **Single-shot prompt with no retrieval grounding.** Produces "John, 35, marketing
   manager" 100% of the time. Always inject niche knowledge_chunks even if they
   are sparse — the very act of conditioning on niche-specific text prevents
   collapse to LLM-default personas.
2. **Free-text `pain_points: str` field.** Validation becomes impossible. Use the
   `PainPoint` model with severity/frequency/addressable_by_offer + the
   reject_platitudes validator.
3. **Single persona for senior verticals.** Documented failure mode. Always
   produce dual personas (senior + adult child) for 55+ home services, medical,
   insurance.
4. **Defaulting income band to middle-class.** Generic AI tools assume
   $60-100k for everyone. Walk-in tub, Medicare, debt-relief, payday — these
   are low-income verticals. Hardcode this awareness in the system prompt.
5. **Treating channel as a string.** "Meta" vs "meta" vs "Facebook" vs
   "facebook_ads" — drift breaks downstream agents. Discriminated union with
   enum prevents this.
6. **Allowing the AI to set `primary_persona_name` to anything.** Always
   validate it appears in `personas`. Use `model_validator`.
7. **No human review loop.** Q-MARKETING-CTX = B already mandates this; do not
   skip the Obsidian export step. Status frontmatter (`status: draft → approved`)
   gates downstream consumption.
8. **Regenerating MarketingContext from scratch when user adds info.** Loses
   detail. Use the merge updater pattern.
9. **Skipping the LLM-as-judge step to save tokens.** The judge runs on
   ~1500 tokens of context for ~$0.0003 on gpt-4o-mini. The cost of one bad
   downstream hypothesis is orders of magnitude higher.
10. **Synthetic personas as "Digital Twins" you can chat with for product
    decisions.** Documented hallucination risk (Digiday April 2026). The persona
    is a *summary spec for human reviewers and downstream agents*, NOT a
    queryable simulated user. Do not build a chat-with-persona feature in MVP.

---

## Recommended starter library set

| Library | Version | Why |
|---|---|---|
| `pydantic` | ^2.8 | Schemas, validators, discriminated unions |
| `pydantic-ai` | latest stable | Agent framework, structured output, retry |
| `pydantic-ai-slim[openai]` | latest | OpenAI-protocol model client (works with OpenRouter via base_url override) |
| `jinja2` | ^3.1 | Prompt templates |
| `sqlalchemy` | ^2.0 | Read-side schema reflection over `marketing_contexts` (Java owns Flyway) |
| `pgvector` | latest | knowledge_chunks vector queries |
| `httpx` | ^0.27 | Async HTTP for OpenRouter |
| `tenacity` | ^8.5 | Retry policies above the Pydantic AI level (network errors) |
| `python-frontmatter` | ^1.1 | Obsidian markdown export with YAML frontmatter |
| `markdown-it-py` | ^3.0 | Optional, for parsing edited Obsidian back to dict |
| `langfuse` | latest | LLM observability — track judge pass-rate over time |
| `pytest` + `pytest-asyncio` | latest | Test harness |
| `dirty-equals` | ^0.7 | Snapshot-friendly assertions for persona output |

OpenRouter configuration: set `OPENAI_BASE_URL=https://openrouter.ai/api/v1`,
`OPENAI_API_KEY=<openrouter_key>`. Pydantic AI's `OpenAIModel("openai/gpt-4o-mini")`
will route through OpenRouter transparently. For the routing decision (per
`alignment/11_TOOLING_MATRIX.md`):
- Drafter: `openai/gpt-4o-mini` (good structured output, cheap)
- Judge: `openai/gpt-4o-mini` (same — keep stack simple)
- Optional escalation for low-confidence drafts: `anthropic/claude-3-5-sonnet`

---

## Open verifications

These need to be checked during Sprint 3 implementation, not assumed:

1. **OpenRouter + Pydantic AI structured output reliability per model.** Tool
   Output mode requires reliable function calling. Some OpenRouter routes
   (especially smaller open-source models) silently return malformed tool
   args. Test the top 3 candidate models against a fixed test set of 20
   briefs and measure: (a) schema validity rate, (b) judge pass rate.
2. **Discriminated-union schema in tool-call JSON.** Pydantic v2 emits a
   discriminator-based JSON Schema, but some LLMs ignore the discriminator
   and produce a hybrid object. Verify with channel_profile specifically.
3. **Token budget for grounding.** 5 chunks at ~500 tokens each = 2500 tokens
   in system prompt. Plus base system prompt (~800) plus user message
   (~600). Within gpt-4o-mini budget but watch context cost on Sonnet
   escalation.
4. **Obsidian round-trip fidelity.** Export MarketingContext to markdown
   with YAML frontmatter, edit by hand, re-import. Verify lossless except
   for explicit user edits. Especially check nested lists (pain_points
   inside personas).
5. **Special Ad Categories warning.** US housing/credit/employment ads block
   age and zip targeting. Verify the system prompt's warning actually fires
   on housing-adjacent niches like senior living. This is a legal compliance
   hint, not a hard block.
6. **JSONB persistence shape.** Pydantic dumps datetime as ISO string;
   PostgreSQL JSONB stores as string. Verify round-trip via SQLAlchemy
   reflection (Python-read-only side per the integration brief).
7. **Behavior when retrieval returns zero chunks.** First user, no Obsidian
   patterns yet. The system prompt currently says "produce conservative
   draft and flag assumptions". Verify this doesn't degrade to generic
   personas — possibly add a fallback to inject a small set of pinned
   "anti-pattern examples" so the model knows what NOT to produce.
8. **Judge pass-rate target.** Initial assumption: 60-70% first-pass after
   one retry, 85%+ after two retries. Measure and tune the judge prompt
   based on real failure modes. Track in Langfuse.
9. **Multi-locale schema readiness.** Schema has `language` field but all
   prompts are English. When/how does Spanish/Portuguese activation work?
   Defer concrete locale work past MVP per scope, but verify schema does
   not bake in English assumptions (no English-only enum values).
10. **Persona update workflow conflict resolution.** The DEEPER-inspired
    updater needs real test cases. Especially: what happens if the user
    says "actually, our buyers are millennial, not 65+"? Should this
    overwrite or split into a new context version?

---

## Sources

### Pydantic AI
- [Pydantic AI Docs — Home](https://ai.pydantic.dev/)
- [Pydantic AI Output API](https://ai.pydantic.dev/api/output/)
- [Pydantic AI Output modes (Tool / Native / Prompted)](https://ai.pydantic.dev/output/)
- [Pydantic AI Multi-Agent Applications](https://ai.pydantic.dev/multi-agent-applications/)
- [Pydantic AI Agent API](https://ai.pydantic.dev/api/agent/)
- [pydantic-ai GitHub](https://github.com/pydantic/pydantic-ai)
- [pydantic-ai-toolsets (Multi-Persona toolset)](https://pypi.org/project/pydantic-ai-toolsets/)
- [Pydantic AI tutorial — DataCamp](https://www.datacamp.com/tutorial/pydantic-ai-guide)
- [Pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/)
- [How to use Pydantic for LLMs](https://pydantic.dev/articles/llm-intro)
- [Structured outputs with Pydantic AI — FreeAgent engineering](https://engineering.freeagent.com/2026/03/24/structured-outputs-with-pydantic-ai/)
- [pydantic-deep — Production deep agents](https://pydantic.dev/articles/pydantic-deep-agents)

### Persona generation tools (build-vs-buy survey)
- [AI User Persona Generator comparison guide — sampl.space](https://sampl.space/blog/ai-user-persona-generator-comparison-guide/)
- [7 Best Buyer Persona Tools 2026 — Marketing Mary](https://www.marketingmary.ai/blog/best-buyer-persona-tools)
- [Delve AI — AI market research](https://www.delve.ai/)
- [Delve AI Persona Generator](https://www.delve.ai/ai-persona-generator)
- [Delve AI Persona review — Research.com](https://research.com/software/reviews/persona-by-delve-ai)
- [Mosai — AI Persona Orchestration Platform](https://www.mosai.eu/)
- [Userdoc — Build better software requirements](https://userdoc.fyi/)
- [Userdoc reviews — SERP AI](https://serp.ai/products/userdoc.fyi/reviews/)
- [UXPressia AI Persona Generator](https://uxpressia.com/ai-persona-generator)
- [FounderPal AI User Persona Generator](https://founderpal.ai/user-persona-generator)
- [UserPersona.dev](https://userpersona.dev/)
- [Personadeck](https://www.personadeck.io/)
- [Inodash AI Persona Generator](https://inodash.com/ai-persona-generator)
- [Top 12 Persona Tools & Templates — Delve AI blog](https://www.delve.ai/blog/persona-template-tools)
- [Emporia Research — Persona Research](https://www.emporiaresearch.com/capabilities/persona-research)
- [NewtonX Persona Research](https://www.newtonx.com/capabilities/customer-segmentation-research/persona-research/)

### Persona generation prompt engineering
- [Orbit Media — 5 Prompts for AI personas](https://www.orbitmedia.com/blog/ai-marketing-personas/)
- [10 ChatGPT Prompt Templates for User Personas — Shushant Lakhyani](https://medium.com/@slakhyani20/10-chatgpt-prompt-templates-that-help-with-user-persona-generation-for-businesses-d09ed967300c)
- [The User Persona Generator Prompt — The Prompt Warrior](https://www.thepromptwarrior.com/p/user-persona-generator-prompt)
- [PersonaTwin — multi-tier prompt conditioning (arXiv 2508.10906)](https://arxiv.org/pdf/2508.10906)
- [Generating Proto-Personas through Prompt Engineering (arXiv 2507.08594)](https://arxiv.org/html/2507.08594v1)
- [PromptHub — Multi-Persona Prompting](https://www.prompthub.us/blog/exploring-multi-persona-prompting-for-better-outputs)
- [Using AI for User Representation — analysis of 83 prompts (arXiv 2508.13047)](https://arxiv.org/html/2508.13047v1)
- [Tuning LLM Personas — Proxet](https://www.proxet.com/blog/using-llms-to-create-personas)
- [Role Prompting — Learn Prompting](https://learnprompting.org/docs/advanced/zero_shot/role_prompting)
- [Persona Prompting — emergentmind](https://www.emergentmind.com/topics/persona-prompting-pp)
- [Prompt engineering best practices 2026 — SuperPrompts](https://superprompts.app/blog/prompt-engineering-best-practices-2026)

### Persona refinement / update workflows
- [DEEPER — Directed Persona Refinement (arXiv 2502.11078)](https://arxiv.org/html/2502.11078)
- [DEEPER ACL 2025](https://aclanthology.org/2025.acl-long.1177.pdf)
- [PersonaDB — collaborative data refinement (arXiv 2402.11060)](https://arxiv.org/html/2402.11060v1)
- [Persona-L for complex needs — CHI 2025](https://dl.acm.org/doi/10.1145/3706598.3713445)
- [Incremental Merge System — DeepWiki](https://deepwiki.com/therealXiaomanChu/ex-skill/4.1-incremental-merge-system)

### LLM-as-judge
- [LLM-as-a-Judge complete guide — Evidently AI](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [LLM-as-a-Judge practical guide — Towards Data Science](https://towardsdatascience.com/llm-as-a-judge-a-practical-guide/)
- [LLM as a Judge for Data Validation — Kadoa](https://www.kadoa.com/blog/llm-as-a-judge)
- [LLM-as-a-Judge — Patronus AI](https://www.patronus.ai/llm-testing/llm-as-a-judge)
- [LLM-as-a-Judge — Confident AI](https://www.confident-ai.com/blog/why-llm-as-a-judge-is-the-best-llm-evaluation-method)
- [Validating LLM simulations as behavioral evidence — Northwestern](https://mucollective.northwestern.edu/files/Hullman-llm-behavioral.pdf)

### Senior + home-services + Meta context
- [Strategic Meta Advertising for Senior Living — DigitalSeniority](https://digitalseniority.com/senior-living-services/meta-advertising)
- [Senior Living Special Ads Category — Mannix Marketing](https://www.mannixmarketing.com/blog/senior-living-special-ads-category/)
- [7 FB Ad Tricks for Senior Living Leads — Sage Age](https://www.sageage.com/blog/facebook-ad-tricks-that-drive-senior-living-leads/)
- [2025 Targeting Restrictions for Seniors — Creating Results](https://creatingresults.com/blog/2025/05/15/targeting-restrictions-on-google-facebook-ads-for-seniors-in-2025/)
- [Maximizing ROI in Senior Living through Google + Meta — CodeDesign](https://codedesign.org/maximizing-roi-senior-living-services-through-google-ads-and-meta-advertising)
- [How to Target Homeowners on FB Ads — Digital Engage](https://digitalengage.net/how-to-target-homeowners-on-facebook-ads/)
- [Lower-income households + life insurance — Consumer Federation](https://consumerfed.org/wp-content/uploads/2017/01/10-1-11-LMI-Life-Insurance_Report.pdf)
- [Health insurance enrollment in low-income contexts — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9121503/)
- [American Family Insurance Persona Marketing at Scale — SlideShare](https://www.slideshare.net/Conductormarketing/persona-marketing-at-scale-american-family-insurance)

### Channel context (Meta vs Google vs TikTok vs Snapchat)
- [Meta vs TikTok Lead Ads — LeadSync](https://leadsync.me/blog/tiktok-vs-meta-lead-ads/)
- [TikTok Lead Generation Objective — TikTok Ads Manager](https://ads.tiktok.com/help/article/lead-generation-objective)
- [TikTok Lead Generation Ads Guide 2025 — NestScale](https://nestscale.com/blog/tiktok-lead-generation-ads.html)
- [Snapchat for Gen Z lead gen — Jordan Digital Marketing](https://www.jordandigitalmarketing.com/blog/snapchat-advertising-the-underrated-gen-z-engagement-platform)
- [How Snapchat / Meta / Pinterest / Google chase TikTok dollars — Digiday](https://digiday.com/marketing/how-snapchat-meta-pinterest-and-google-are-eyeing-up-tiktok-ad-dollars/)
- [Best Converting Landing Pages — Dating + Casino — Brax](https://www.brax.io/blog/best-converting-landing-pages-analyzed-dating-and-casino)
- [Top 7 Dating Landing Pages 2026 — ROI Ads](https://roiads.co/blog/dating-landing-page-and-pre-landing-examples/)

### JTBD + persona theory
- [Personas vs JTBD — Nielsen Norman Group](https://www.nngroup.com/articles/personas-jobs-be-done/)
- [Adding JTBD to a persona-based product process — JTBD.org](https://jobstobedone.org/radio/jobs-to-be-done-and-personas/)
- [Personas and JTBD — Delve AI blog](https://www.delve.ai/blog/personas-jobs-to-be-done)
- [54 Templates for Personas + JTBD — User Interviews](https://www.userinterviews.com/blog/templates-personas-jtbd-mental-models)

### Anti-patterns and safeguards
- [Comparing AI Buyer Personas — Mnemonic.ai](https://mnemonic.ai/blog/buyer-persona-creation-with-ai-part-2-should-you-use-public-llms-for-persona-creation/)
- [AI personas promise speed but need safeguards — Digiday](https://digiday.com/marketing/ai-personas-promise-speed-but-safeguards-are-need-to-avoid-leading-marketers-astray/)
- [How to use AI-powered personas — YouGov](https://yougov.com/guides/53560-how-to-use-ai-powered-customer-personas-for-marketing)
