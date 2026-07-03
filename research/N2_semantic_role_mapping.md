# Node N2 — Semantic Role Mapping Research

> Vision LLM analyzes screenshot + DOM elements → identifies semantic roles per element
> (`primary_cta`, `hero_image`, `lead_form`, `trust_block`, `phone_block`, `headline`,
> `social_proof_block`, `before_after`, `pricing_block`, etc.) with confidence scores
> and bounding boxes. Snapshot input from N1 (Firecrawl) — markdown + raw HTML +
> screenshot + DOM elements with positions.

---

## TL;DR

**For Ruflo's lead-gen landing page domain (home improvement, dating), the right architecture for N2 is a hybrid: lightweight DOM pre-filter → screenshot+DOM-annotated prompt → Pydantic AI agent against `claude-sonnet-4.x` via OpenRouter, with `gpt-4o` as a cross-validation fallback.** Pure vision-only approaches still under-perform on small/dense UI elements (best ScreenSpot-Pro grounding score is ~48% with specialized search models, vs. ~18-39% for general MLLMs and OmniParser v2). DOM hints close that gap dramatically — Skyvern-style hybrid systems hit ~85% on WebGames. Coordinate hallucination is real but is mitigated by (a) Set-of-Mark (SoM) overlays where you draw numbered boxes on the screenshot derived from `getBoundingClientRect()`, then ask the model to *label by number*, not *predict pixels*, and (b) constraining outputs through a tight Pydantic schema with `Literal`-typed roles and `confidence: float = Field(ge=0, le=1)`.

OmniParser v2 is **production-grade for icon/text element detection but it does not classify semantic roles** — it gives you "this is a clickable region containing the text 'Get Estimate'", not "this is a `primary_cta`". Use it as a *pre-processor* (free, local, fast) feeding marks into the vision LLM, not as a replacement.

Cost target ($0.20-0.50/snapshot) is achievable with Claude Sonnet 4.x: image input is roughly $0.0048/image plus 500-1500 input tokens for the schema/instructions and 300-800 output tokens, landing around **$0.02-0.06 per snapshot** with Sonnet, $0.05-0.12 with Opus, $0.01-0.03 with GPT-4o. The $0.20-0.50 budget is comfortable headroom for a multi-pass approach (vision call + validator call + optional Opus arbitration when conflicts arise).

**Build vs buy verdict: BUILD on top of OmniParser v2 (open source, MIT) + Pydantic AI + Claude Sonnet via OpenRouter.** No vendor sells "lead-gen landing page semantic role tagging" as a product, and the role taxonomy is domain-specific to Ruflo.

---

## Top 5 existing solutions

### 1. Microsoft OmniParser v2 (Feb 2025) — RECOMMENDED PRE-PROCESSOR

- **What it is:** A YOLOv8-based interactable region detector + a fine-tuned Florence-2-base captioner. Outputs bounding boxes around all clickable/interactable elements with functional descriptions. MIT-licensed, runs locally.
- **Benchmark:** 39.5% on ScreenSpot-Pro (SoTA for general-purpose grounding; specialized models like ScreenSeekeR hit 48.1%).
- **Speed:** 0.6s/frame on A100, 0.8s on RTX 4090. Reports of running on T4 (16GB) on Replicate.
- **VRAM:** 12GB minimum reported as tight, 24GB comfortable. Florence-2-base is ~230M params, YOLOv8 is small. Realistic floor is ~10-12GB.
- **What it does NOT do:** Semantic role labeling like "this is a hero image" or "this is the primary CTA". It tells you "icon at (x,y,w,h) is described as 'Get a Free Quote button'". You still need an LLM to map that to your role taxonomy.
- **Production-ready:** Yes for the detection layer. Used in production-grade computer-use agents (Magentic-One, etc.). Available on Replicate API for $-per-run if you don't want to self-host.
- **URL:** https://github.com/microsoft/OmniParser, https://huggingface.co/microsoft/OmniParser-v2.0

### 2. Set-of-Mark (SoM) Prompting (Microsoft, 2023, still SoTA technique)

- **What it is:** A *prompting pattern*, not a tool. Overlay numbered boxes on the screenshot before sending to GPT-4V/Claude, then ask the model to refer to elements by number rather than predicting coordinates. SEEM/SAM produces the segments in the original paper, but for web you can derive marks directly from `getBoundingClientRect()` (you already have DOM positions from Firecrawl).
- **Why it matters:** Outperforms fully fine-tuned referring expression models on RefCOCOg in zero-shot. *This is the single highest-leverage technique to copy.*
- **URL:** https://github.com/microsoft/SoM, https://arxiv.org/abs/2310.11441

### 3. ScreenAI (Google, IJCAI 2024) — RESEARCH ONLY, NOT OSS

- **What it is:** 5B-param vision-language model specialized for UI/infographics. SoTA on Multi-page DocVQA, WebSRC, MoTIF, Widget Captioning at release.
- **Status:** **Weights not released.** Research artifact. Not usable directly. Mentioned because it's the architectural blueprint many later models follow.
- **URL:** https://dl.acm.org/doi/10.24963/ijcai.2024/339

### 4. ScreenAgent (IJCAI-24) — FLAG: APPEARS DORMANT

- **What it is:** Visual agent for desktop control with task planning, image understanding, visual positioning.
- **Status:** Last meaningful repo activity was around the IJCAI-24 publication. Not maintained for general production use as of 2026. Useful as a reference architecture, not a dependency.
- **URL:** https://github.com/niuzaisheng/ScreenAgent

### 5. SeeAct / Mind2Web (OSU NLP) + WebVoyager benchmarks

- **What it is:** SeeAct is the canonical reference for "GPT-4V as web agent if grounded properly." Mind2Web and Online-Mind2Web are the benchmark suites. The 2025 "Illusion of Progress" paper (COLM 2025, arxiv 2504.01382) found that **only Claude Computer Use 3.7 and OpenAI Operator beat the original SeeAct baseline** on Online-Mind2Web (300 tasks across 136 sites). Operator tops out at ~61% success.
- **Why it matters for Ruflo:** Confirms grounding is the bottleneck (20-25% gap vs. oracle grounding). Validates the hybrid DOM+vision approach that Computer Use 3.7 uses internally.
- **URL:** https://osu-nlp-group.github.io/SeeAct/, https://arxiv.org/html/2504.01382v4

### Honorable mentions worth a look

- **Skyvern** (https://github.com/Skyvern-AI/skyvern) — open source, hybrid DOM+vision web agent, hits ~85% on WebGames using accessibility tree + selective vision. Architecture worth studying even if you don't adopt the framework.
- **CogAgent / SeeClick / SE-GUI** — open-weights GUI grounding models. SE-GUI (May 2025) hit 47.2% on ScreenSpot-Pro at 7B params trained on only 3k samples. Useful for cost-sensitive cases where you can't pay LLM-per-image fees.

---

## Code references worth studying

| Project | What to copy | URL |
|---|---|---|
| `microsoft/OmniParser` (`util/omniparser.py`) | Image preprocessing + box-merging logic; how they de-duplicate overlapping detections | https://github.com/microsoft/OmniParser |
| `microsoft/SoM` (`task_adapter/som.py`) | Mark generation, alphanumeric overlay rendering, prompt templates | https://github.com/microsoft/SoM |
| `Skyvern-AI/skyvern` (`skyvern/forge/sdk/api/llm/prompts/`) | Production-grade prompt templates that combine DOM + screenshot for element targeting | https://github.com/Skyvern-AI/skyvern |
| `OSU-NLP-Group/SeeAct` | Two-stage planning→grounding architecture, JSON action schemas | https://github.com/OSU-NLP-Group/SeeAct |
| `pydantic/pydantic-ai` (examples in `examples/pydantic_ai_examples/`) | Vision input pattern via `BinaryContent` and `ImageUrl`; multi-output `Union` types | https://github.com/pydantic/pydantic-ai |

---

## Production case studies (if any)

- **Anthropic Claude Computer Use 3.5/3.7** (Oct 2024 / Feb 2025) — first major production vision agent. Internally uses screenshot + coordinate-aware prompting. The fact that this is the only model alongside Operator to beat 2024-era SeeAct on Online-Mind2Web tells you the bar is high. Anthropic has not published their grounding strategy in detail.
- **OpenAI Operator** (Jan 2025) — vision-only computer-use agent, ~61% on Online-Mind2Web. Confirms even frontier vision-only systems are imperfect at element grounding without DOM hints.
- **Skyvern** (production deployments at multiple SaaS companies) — open-source case study of hybrid DOM+vision at scale. ~85% WebGames.
- **HubSpot Breeze AI for CTA generation** (2025) — closest commercial product to Ruflo's domain, but generates CTAs rather than detecting them. Not a competitor for the *detection* node.

No public production case study exists for "vision LLM detecting semantic roles on lead-gen landing pages." This is greenfield and confirms BUILD over BUY.

---

## Build vs buy verdict

**BUILD.** Justification:

1. **No commercial product covers the problem shape.** OmniParser detects regions but doesn't classify them into Ruflo's domain-specific role taxonomy (`primary_cta` vs. `phone_block` vs. `before_after` is a marketing-domain ontology, not a generic UI ontology).
2. **The taxonomy will evolve.** Lead-gen home-improvement landing pages have niche roles (`before_after` photo carousels, `financing_calculator`, `service_area_map`) that you'll iterate on as you generate more hypotheses. A vendor product would lock you in.
3. **Cost is favorable.** Per-snapshot cost on Claude Sonnet 4.x via OpenRouter is well below the $0.20-0.50 ceiling, leaving room for a multi-pass approach (detect → classify → validate).
4. **The hard parts are solved upstream.** Region detection is solved (OmniParser). Structured output is solved (Pydantic AI). Only the role classification + validation logic is bespoke, and it's small.

**Stack:**
- **Detection (optional, for higher accuracy):** OmniParser v2 self-hosted on a GPU instance OR Replicate API.
- **Classification:** Pydantic AI agent → OpenRouter → `anthropic/claude-sonnet-4.6` (primary), `openai/gpt-4o` (fallback/cross-check).
- **Arbitration (rare, for low-confidence cases):** Pydantic AI agent → `anthropic/claude-opus-4.6` for ambiguous snapshots.
- **Coordinate strategy:** Use `getBoundingClientRect()` from N1's DOM data → render SoM marks → ask LLM to label *by mark number*, never *by predicting pixels*.

---

## Concrete patterns to copy

### Pydantic schema for `SemanticRole` output

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

SemanticRoleType = Literal[
    "primary_cta",
    "secondary_cta",
    "hero_image",
    "hero_headline",
    "hero_subheadline",
    "lead_form",
    "phone_block",
    "trust_block",
    "social_proof_block",
    "testimonial_block",
    "before_after",
    "pricing_block",
    "service_list",
    "faq_block",
    "guarantee_block",
    "credentials_block",
    "footer_block",
    "navigation",
    "unknown",
]


class BoundingBox(BaseModel):
    """Pixel coordinates relative to the rendered viewport."""
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class RoleAssignment(BaseModel):
    """One semantic role assigned to one DOM element / region."""
    mark_id: int = Field(
        description="The Set-of-Mark ID overlaid on the screenshot. "
                    "Refers back to the DOM element list."
    )
    role: SemanticRoleType
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Only present if the element is image-like (hero, before_after) "
                    "and the model needs to refine the box beyond the DOM rect."
    )
    rationale: str = Field(
        max_length=240,
        description="One sentence: why this element earned this role."
    )


class PageSemanticMap(BaseModel):
    """Full semantic map for one snapshot (one viewport, e.g. desktop OR mobile)."""
    viewport: Literal["desktop", "mobile"]
    page_archetype: Literal[
        "lead_capture",
        "service_explainer",
        "pricing_focused",
        "trust_first",
        "video_first",
        "long_form_sales",
        "other",
    ]
    archetype_confidence: float = Field(ge=0.0, le=1.0)
    assignments: list[RoleAssignment]
    notes: str = Field(
        default="",
        max_length=600,
        description="Anything notable that doesn't fit a role (animations, "
                    "exit intent popups present in DOM, etc.)"
    )

    @model_validator(mode="after")
    def exactly_one_primary_cta(self):
        primaries = [a for a in self.assignments if a.role == "primary_cta"]
        if len(primaries) > 1:
            # Keep only the highest-confidence primary; demote the rest.
            primaries.sort(key=lambda a: a.confidence, reverse=True)
            for demoted in primaries[1:]:
                demoted.role = "secondary_cta"
        return self

    @model_validator(mode="after")
    def at_most_one_hero_image(self):
        heroes = [a for a in self.assignments if a.role == "hero_image"]
        if len(heroes) > 1:
            heroes.sort(key=lambda a: a.confidence, reverse=True)
            for demoted in heroes[1:]:
                demoted.role = "unknown"
        return self
```

### Vision LLM prompt template (system + user)

```python
SYSTEM_PROMPT = """\
You are a senior conversion-rate-optimization analyst. You classify
elements of LEAD-GENERATION landing pages (home-improvement services,
dating sites, similar verticals) into a fixed semantic-role taxonomy.

You will receive:
1. A screenshot with numbered marks overlaid on every interactive or
   structurally important element. Each mark is a small numbered badge
   in the top-left corner of that element's bounding box.
2. A JSON list of those marks: [{mark_id, tag, text, role_attr,
   bounding_box}, ...] derived from the DOM. The mark numbers in the
   image MATCH the mark_ids in the JSON.
3. The viewport context (desktop or mobile).

RULES (violating these will fail validation):
- The PRIMARY CTA is the single button/link the page is most clearly
  optimized to drive clicks toward. There is at most ONE per snapshot.
  If two equally prominent buttons exist (e.g., "Get Quote" and "Call
  Now"), choose the one closer to the hero and demote the other to
  `secondary_cta` or `phone_block`.
- HERO IMAGE is the largest above-the-fold visual that establishes
  the offer. At most ONE per snapshot. Background videos count.
- LEAD FORM is any form whose primary purpose is collecting contact
  info for follow-up (name/email/phone/zip). Search bars and login
  forms do NOT count.
- TRUST BLOCK = badges, certifications, "BBB A+", "X years in
  business", media logos. Distinct from SOCIAL PROOF BLOCK
  (testimonials, reviews, star ratings, customer counts).
- BEFORE_AFTER = paired images showing transformation, common in
  home-improvement (roofing, kitchens, bathrooms).
- Refer to elements by mark_id. Do not invent mark_ids that aren't
  in the input list.
- Confidence < 0.5 means "I'm guessing" — set role to `unknown`
  unless you have a clear textual or visual signal.
- Be conservative. `unknown` is preferable to a wrong label.
"""


USER_PROMPT_TEMPLATE = """\
Viewport: {viewport}
URL: {url}
Page archetype hints from N1 (markdown headings): {h1_h2_summary}

Marks list (JSON):
{marks_json}

Classify every mark into a role. Return a PageSemanticMap.
"""
```

### Pydantic AI agent definition

```python
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

semantic_mapper_agent = Agent(
    model=OpenAIModel(
        "anthropic/claude-sonnet-4.6",
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    ),
    output_type=PageSemanticMap,
    system_prompt=SYSTEM_PROMPT,
    model_settings={"temperature": 0.0},  # deterministic classification
    retries=2,  # Pydantic-AI auto-retries on validation failure
)


async def classify_snapshot(snapshot: Snapshot) -> PageSemanticMap:
    marked_image_bytes = render_set_of_marks(
        screenshot=snapshot.screenshot_bytes,
        dom_elements=snapshot.dom_elements,
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        viewport=snapshot.viewport,
        url=snapshot.url,
        h1_h2_summary=extract_headings(snapshot.markdown)[:500],
        marks_json=json.dumps(
            [m.model_dump() for m in snapshot.dom_elements],
            ensure_ascii=False,
        ),
    )

    result = await semantic_mapper_agent.run(
        [
            user_prompt,
            BinaryContent(data=marked_image_bytes, media_type="image/png"),
        ]
    )
    return result.output
```

### Validation logic snippet (cross-check + low-confidence arbitration)

```python
async def classify_with_validation(
    snapshot: Snapshot,
    arbitrate_below: float = 0.6,
) -> PageSemanticMap:
    # 1. Primary classification on Sonnet.
    primary = await classify_snapshot(snapshot)

    # 2. If primary CTA confidence is low OR archetype confidence is
    #    low, run a cross-check on GPT-4o.
    primary_cta_conf = next(
        (a.confidence for a in primary.assignments if a.role == "primary_cta"),
        0.0,
    )
    if (
        primary.archetype_confidence < arbitrate_below
        or primary_cta_conf < arbitrate_below
    ):
        cross_check = await classify_snapshot_via(
            snapshot, model="openai/gpt-4o"
        )
        if not _agree_on_primary_cta(primary, cross_check):
            # 3. Arbitrate disagreement on Opus.
            primary = await classify_snapshot_via(
                snapshot,
                model="anthropic/claude-opus-4.6",
                extra_context={
                    "sonnet_says": primary.model_dump(),
                    "gpt4o_says": cross_check.model_dump(),
                },
            )
    return primary


def _agree_on_primary_cta(a: PageSemanticMap, b: PageSemanticMap) -> bool:
    a_cta = next((x.mark_id for x in a.assignments if x.role == "primary_cta"), None)
    b_cta = next((x.mark_id for x in b.assignments if x.role == "primary_cta"), None)
    return a_cta is not None and a_cta == b_cta
```

---

## Anti-patterns

1. **Asking the LLM to predict pixel coordinates of bounding boxes.** This is the #1 source of hallucination in vision LLMs. Coordinates from frontier models drift 20-50px on dense pages and routinely invent boxes for non-existent elements. **Always derive boxes from DOM (`getBoundingClientRect`) and have the LLM label by `mark_id`.** Only use LLM-predicted boxes when no DOM element exists (e.g., refining the visual subject of a hero photo).
2. **Sending the raw screenshot with no DOM context.** Pure-vision underperforms hybrid by 15-25% on web grounding tasks (Skyvern, SeeAct findings). You already have DOM from Firecrawl — use it.
3. **Letting "primary_cta" appear multiple times.** A landing page by definition has one. Enforce in Pydantic with a `model_validator` (shown above) that demotes duplicates.
4. **One-shot examples in the prompt that show the WRONG role taxonomy.** Few-shot bias is severe on vision LLMs. If you provide examples, every example must use *exactly* the role taxonomy in your `Literal` type. Better: zero-shot with a tight schema; trust the model's prior.
5. **Treating mobile and desktop as the same input.** A side-nav on desktop becomes a hamburger menu on mobile; a horizontal trust-bar becomes a stacked block; the primary CTA may move from header to sticky-bottom. Run N2 separately for each viewport snapshot and store separate `PageSemanticMap` objects.
6. **Trusting OmniParser's text labels for role classification.** OmniParser's Florence-2 captioner gives functional descriptions ("Get a Free Quote button"), not taxonomic roles. Use OmniParser only for *region detection*, not *role assignment*.
7. **Using temperature > 0 for classification.** This is a structured-extraction task. Use `temperature=0.0` and rely on `retries=2` in Pydantic AI for any transient JSON-shape failures.
8. **Hallucination "every button is primary_cta."** Mitigation: explicit RULES block in the system prompt forbidding it, plus the `model_validator` enforcement, plus low-confidence demotion to `unknown`.
9. **Not flagging missing roles.** A page with no detected `lead_form` on a lead-gen vertical is suspicious — N1 may have failed to render a JS-injected form. Surface this as a quality signal upstream rather than silently producing an empty `lead_form` slot.
10. **Skipping the cost ceiling check.** OpenRouter has per-provider price drift; gate snapshot processing on `expected_cost_usd` and abort if a single snapshot would exceed the per-snapshot budget (e.g., very tall pages with many elements blowing up the input-token count).

---

## Recommended starter library set

```toml
# pyproject.toml fragment
[project]
dependencies = [
    "pydantic>=2.7",
    "pydantic-ai>=0.0.30",          # vision input + retries
    "httpx>=0.27",
    "pillow>=10.4",                 # SoM mark rendering
    "tenacity>=9.0",                # outer retry around OpenRouter
    "structlog>=24.4",              # structured logs for cost/latency
]

[project.optional-dependencies]
omniparser = [
    # Self-hosted detection. Optional — only if you choose to run
    # OmniParser locally instead of using Replicate.
    "torch>=2.4",
    "transformers>=4.45",
    "ultralytics>=8.3",
    "huggingface-hub>=0.25",
]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "respx>=0.21",                  # mock OpenRouter in tests
    "ruff>=0.6",
    "mypy>=1.11",
]
```

Don't add: `langchain` (you already have LangGraph upstream; don't double-import), `instructor` (Pydantic AI covers the same need with first-class image support).

---

## Open verifications

These are claims I could not fully verify in this research pass — surface them in your build plan as test-it-yourself items:

1. **Exact OmniParser v2 VRAM floor for 1440×900 web screenshots.** Reports vary 12-24GB. Bench it on your target screenshot resolution before committing to a self-host plan.
2. **Claude Sonnet 4.x vs GPT-4o on `primary_cta` disambiguation specifically.** Existing benchmarks (ScreenSpot-Pro, WebVoyager) measure clickability, not semantic role. Build a 50-page hand-labeled eval set from your home-improvement and dating verticals and run both models. Anecdotally Claude is stronger on "which of these two equally prominent buttons is the primary CTA?" judgment calls, but verify.
3. **Whether SoM marks improve or hurt accuracy on dense lead-gen pages.** SoM is well-established for desktop GUI grounding, but on long, dense landing pages with 80+ marks the visual clutter may degrade performance. Test with marks vs. without; consider a "top-N most likely candidates from DOM heuristics + marks only on those" hybrid.
4. **Whether OmniParser as a pre-filter actually reduces the LLM's mark count enough to justify the latency cost.** OmniParser adds 0.6-0.8s per snapshot. If your DOM-derived marks are already clean (Firecrawl element list is good), OmniParser may be redundant.
5. **OpenRouter provider variance on Sonnet image input pricing.** OpenRouter routes to multiple providers; per-image surcharges differ. Lock to a single provider via `provider` routing config if cost predictability matters.
6. **Whether Opus arbitration is worth it.** Opus is ~5x Sonnet cost. Run a 100-snapshot eval where Opus arbitrates Sonnet/GPT-4o disagreements and measure label-flip rate. If flips are <10%, consider just trusting Sonnet's higher-confidence assignment and skipping Opus.
7. **Confidence calibration.** LLM-reported confidence is notoriously poorly calibrated. Build a calibration set: sample 200 assignments with reported confidence in each decile, hand-label correctness, and fit an isotonic regression to get *actual* probabilities. Don't trust raw `confidence` from the LLM for downstream gating.
8. **Mobile vs desktop role consistency.** Hypothesis: on lead-gen pages, the primary CTA stays semantically identical across viewports (same DOM node, different position). Verify, because if it holds you can save half the LLM calls by classifying desktop only and projecting roles onto mobile via DOM identity.

---

## Sources

- [Microsoft OmniParser (GitHub)](https://github.com/microsoft/OmniParser)
- [OmniParser V2: Turning Any LLM into a Computer Use Agent — Microsoft Research](https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/)
- [microsoft/OmniParser-v2.0 — Hugging Face](https://huggingface.co/microsoft/OmniParser-v2.0)
- [microsoft/omniparser-v2 on Replicate](https://replicate.com/microsoft/omniparser-v2)
- [OmniParser v2 hardware/VRAM discussion (issue #31)](https://github.com/microsoft/OmniParser/issues/31)
- [Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V (arXiv 2310.11441)](https://arxiv.org/abs/2310.11441)
- [microsoft/SoM (GitHub)](https://github.com/microsoft/SoM)
- [SoM-GPT4V demo site](https://som-gpt4v.github.io/)
- [ScreenAI: A Vision-Language Model for UI and Visually-Situated Language Understanding (arXiv 2402.04615)](https://www.emergentmind.com/papers/2402.04615)
- [ScreenAI ACM/IJCAI 2024](https://dl.acm.org/doi/10.24963/ijcai.2024/339)
- [ScreenAgent (GitHub)](https://github.com/niuzaisheng/ScreenAgent)
- [ScreenSpot-Pro: GUI Grounding for Professional High-Resolution Computer Use (arXiv 2504.07981)](https://arxiv.org/html/2504.07981v1)
- [ScreenSpot-Pro Leaderboard](https://gui-agent.github.io/grounding-leaderboard/)
- [SeeAct project page](https://osu-nlp-group.github.io/SeeAct/)
- [GPT-4V(ision) is a Generalist Web Agent, if Grounded (arXiv 2401.01614)](https://arxiv.org/html/2401.01614v1)
- [An Illusion of Progress? Assessing the Current State of Web Agents (COLM 2025, arXiv 2504.01382)](https://arxiv.org/html/2504.01382v4)
- [Mind2Web (NeurIPS 2023)](https://github.com/OSU-NLP-Group/Mind2Web)
- [Mind2Web Live (SeeAct V) — boyugou](https://github.com/boyugou/Mind2Web_Live_SeeAct_V)
- [Skyvern-AI/skyvern (GitHub)](https://github.com/Skyvern-AI/skyvern)
- [Building Browser Agents: Architecture, Security, and Practical Solutions (arXiv 2511.19477)](https://arxiv.org/pdf/2511.19477)
- [Pydantic AI Output Docs](https://ai.pydantic.dev/output/)
- [Pydantic AI Image/Audio/Video/Document Input](https://ai.pydantic.dev/input/)
- [Pydantic AI structured outputs with multimodal LLMs (DEV.to)](https://dev.to/stephenc222/how-to-use-pydanticai-for-structured-outputs-with-multimodal-llms-3j3a)
- [Building a product search API with GPT-4 Vision, Pydantic, and FastAPI (Pydantic blog)](https://pydantic.dev/articles/llm-vision)
- [Pydantic Validators Docs](https://docs.pydantic.dev/latest/concepts/validators/)
- [Holistic Analysis of Hallucination in GPT-4V(ision): Bias and Interference Challenges (arXiv 2311.03287)](https://ar5iv.labs.arxiv.org/html/2311.03287)
- [Awesome-LVLM-Hallucination (GitHub)](https://github.com/NishilBalar/Awesome-LVLM-Hallucination)
- [Can GPT-4o Evaluate Usability Like Human Experts? (arXiv 2506.16345)](https://arxiv.org/html/2506.16345v1)
- [Learning to Localize Objects Improves Spatial Reasoning in Visual-LLMs (arXiv 2404.07449)](https://arxiv.org/html/2404.07449v1)
- [OpenRouter Pricing](https://openrouter.ai/pricing)
- [Claude Sonnet 4.6 — OpenRouter](https://openrouter.ai/anthropic/claude-sonnet-4.6)
- [Claude Opus 4.6 — OpenRouter](https://openrouter.ai/anthropic/claude-opus-4.6)
- [40+ Latest Call to Action Statistics for 2025 (Sender)](https://www.sender.net/blog/call-to-action-statistics/)
- [The Ultimate Guide to CTA Testing (ezbot.ai)](https://www.ezbot.ai/post/the-ultimate-guide-to-cta-testing)
- [Free AI CTA Generator for Landing Pages (Landingi)](https://landingi.com/marketing-resources/ai-cta-generator-for-landing-pages/)
- [Automatically Detecting Reflow Accessibility Issues in Responsive Web Pages (ICSE 2024)](https://dl.acm.org/doi/10.1145/3597503.3639229)
