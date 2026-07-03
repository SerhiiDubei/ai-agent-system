# Node N7 — Hypothesis Builder & Output Research

> Standalone Python multi-agent system for A/B-test hypothesis generation.
> Scope of N7: take the top-ranked proposal from N6 Decision Engine, expand it into a full
> `HypothesisSpec` (Pydantic), serialize to a Markdown file in an Obsidian vault under
> `01_Projects/<client>/proposals_YYYY-MM-DD.md`, watch the file for status changes
> (`pending → approved | rejected | modified → shipped`) and trigger downstream actions.

---

## TL;DR

- **Build the spec layer in Pydantic v2; render with Jinja2; persist as Markdown with YAML frontmatter.** This is the de-facto stack for "structured-data → human-readable doc" in 2026 (used by `settings-doc`, RenderCV, MyST, Instructor, every static-site generator). Round-trip integrity (Markdown ↔ Pydantic) is provided by `python-frontmatter` + a Pydantic validator on the loaded dict.
- **Use `python-statemachine` (not `transitions`) for the status workflow.** It is class-based, integrates cleanly with Pydantic models, gives stricter validity guarantees, and exposes hooks (`on_enter_*`, `on_exit_*`) that map 1:1 to the downstream side-effects the system needs (notify Java Assistant, write history row, etc.). `transitions` is more flexible but its dynamic monkey-patching makes auditability and type-checking harder — a bad fit for an audited pipeline.
- **Use `watchdog` (PollingObserver fallback on Windows) + a 1.5 s timestamp-debounce per file.** Obsidian on Windows triggers up to 5 events per save. Polling is mandatory if the vault sits on a network share / iCloud / Dropbox folder.
- **Adopt the GrowthBook hypothesis vocabulary directly** (`hypothesis`, `goal_metrics`, `secondary_metrics`, `guardrail_metrics`, `variations`) so the eventual handoff to GrowthBook via the existing Java Assistant is a flat field-mapping, not a semantic translation. Treat your `HypothesisSpec` as a superset that adds `change_level L1-L4`, `evidence`, `reasoning`, `risk_level` — fields GrowthBook doesn't natively model.
- **Non-destructive by default.** Rejected proposals are *moved* to an archive sub-folder, not deleted, with a `decision_status: rejected` and `rejection_reason` in frontmatter. Modified proposals get a sibling `_v2.md` and the original is marked `superseded_by`. This mirrors dbt's model-versioning playbook and Azure blob-versioning guidance.
- **Markdown layout: TL;DR up top, frontmatter as the source of truth for status, reasoning trace as a collapsible details block at the bottom.** Mirrors the GitHub PR convention reviewers already know.
- **Bulk approval = a single `proposals_YYYY-MM-DD.md` index file** with a Dataview-rendered table of every per-proposal note. Status is changed in the per-proposal frontmatter; the index re-renders automatically. This avoids needing a custom UI while still giving the user a one-screen approve-many UX.

---

## Top 5 existing solutions (and what to steal from each)

| # | Tool / library | What it does well | What we copy |
|---|---|---|---|
| 1 | **GrowthBook** (REST API + UI) | Industry-standard CRO platform. Defines `hypothesis`, `goal_metrics`, `secondary_metrics`, `guardrail_metrics`, `variations`, `tags`, `description` as first-class fields. Offers safe-rollout with auto-rollback on guardrail breach. | Field names (so handoff is trivial), the goal/secondary/guardrail trichotomy, and the safe-rollout semantics for the eventual M14 adapter. |
| 2 | **Optimizely Feature Experimentation** (datafile schema) | Versioned JSON datafile with `experiments[].variations[]`, `audiences`, `traffic_allocation`. Treats variations as immutable once shipped. | Immutability of shipped variations; `variation_id` separate from semantic name. |
| 3 | **VWO** (CRO roadmap export) | Roadmap CSV/JSON contains `test_name`, `description`, `hypothesis`, `observation`, `target_page`, `expected_lift`, `priority_score`. | The "observation → hypothesis → expected lift" narrative ordering for the Markdown body. |
| 4 | **dbt model versioning** | `version`, `deprecation_date`, `latest_version`, `defined_in` properties on every model. Producers own deprecation; consumers get migration windows. | The `superseded_by` / `deprecation_date` fields in our frontmatter for the Modified-after-shipped case. |
| 5 | **Opik / LangSmith / Langfuse thread-level review** | Reviewers can open a trace, score, leave threaded comments, and tag issues. Comments are first-class data that flows back into the eval loop. | Comments as a `## Discussion` section appended below `## Reasoning Trace`, with attribution + timestamp. Each comment becomes a `feedback_event` row in M15 FeedbackLoopService. |

---

## Code references worth studying

- **`eyeseast/python-frontmatter`** — the canonical YAML-frontmatter loader. `frontmatter.load()` gives you a `Post` whose `.metadata` is a dict you can pass straight into `HypothesisSpec.model_validate(...)`. Round-trips losslessly when you `frontmatter.dumps(post)`.
- **`radeklat/settings-doc`** — concrete reference for "Pydantic model → Jinja2 template → Markdown" with a CLI. Their `templates/markdown.jinja2` is ~40 lines and worth reading verbatim.
- **`Frefreak/mdantic`** — Python-Markdown extension that renders any Pydantic model as a Markdown table. Useful if we want auto-generated schema docs for ops.
- **`rendercv/rendercv`** — proves the pattern at scale: Pydantic for validation, Jinja2 for rendering, custom filters for date/markdown formatting. Multiple output formats from one source of truth.
- **`pytransitions/transitions`** vs **`fgmacedo/python-statemachine`** — read both quick-starts; the second is what we want for an auditable proposal lifecycle.
- **`gorakhargosh/watchdog`** issues #309 and #346 — read these before writing the file watcher; they document the "multiple-events-per-save" gotcha that will bite you on Windows and on macOS Atomic Save editors.
- **`lazydog`** (built on watchdog) — implements event aggregation. If our debounce gets hairy, swap the raw `Observer` for `LazyObserver`.
- **GrowthBook REST API docs** (`/api/v1/experiments`) — copy the request body shape; that's our future M14 payload.

---

## Production case studies

- **Booking.com / Airbnb internal experiment platforms** (publicly described in engineering blogs): both maintain a "hypothesis registry" separate from the experiment runner. Hypotheses live in version-controlled YAML/Markdown; only approved hypotheses become experiments. This is exactly the N7 → M14 split we're building.
- **dbt Mesh** (dbt Labs): producer/consumer model with explicit `deprecation_date`, `latest_version`, `defined_in` properties. Direct precedent for our non-destructive Modify flow.
- **GitLab deprecations docs** (`docs.gitlab.com/update/deprecations/`): every deprecated feature carries `announced_in`, `removed_in`, `breaking_change`, `migration_guide` — same shape we want for `decision_status: rejected | superseded`.
- **Comet Opik thread-level annotation**: human-in-the-loop approval workflow with `approve | edit | reject` actions, threaded comments, custom rubrics. The closest open-source analog to the human-review UX we want via Obsidian.

---

## Build vs. buy verdict

**Build** the N7 service in-house. Reasons:

1. The Pydantic + Jinja2 + python-frontmatter + watchdog stack is ~300 LOC of glue. No off-the-shelf tool covers the *combination* of (a) Obsidian-vault output, (b) custom `HypothesisSpec` schema, (c) status-machine integration with our own `agent_runs` / `decision_runs` tables.
2. The closest "buy" candidates (GrowthBook UI, Opik, LaunchDarkly) all assume their own data model. Adopting any of them as the proposal store would mean translating our spec into their domain and back, doubling the schema drift surface.
3. We *do* buy the underlying primitives (Pydantic v2, Jinja2, python-statemachine, python-frontmatter, watchdog). All MIT/BSD/Apache, all stable, all covered by our existing tooling.

**Caveat:** if review-throughput grows beyond ~50 proposals/week, revisit Streamlit or Retool as a second-window UI. Obsidian-as-UI is right for MVP (per Q-REVIEW-UX = B) but doesn't scale to multi-reviewer with real-time conflict resolution.

---

## Concrete patterns to copy

### 1. Complete Pydantic `HypothesisSpec` model

```python
# src/n7/models.py
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, HttpUrl, field_validator
import uuid


class ChangeLevel(str, Enum):
    L1_CONTENT_SWAP    = "L1_CONTENT_SWAP"     # copy / value prop edit
    L2_ASSET_SWAP      = "L2_ASSET_SWAP"       # image, icon, video
    L3_STYLE_EMPHASIS  = "L3_STYLE_EMPHASIS"   # color, typography, spacing
    L4_COMPONENT_ADD   = "L4_COMPONENT_ADD"    # new section / module


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DecisionStatus(str, Enum):
    pending      = "pending_human_review"
    approved     = "approved"
    rejected     = "rejected"
    modified     = "modified"
    shipped      = "shipped"
    superseded   = "superseded"   # non-destructive replacement of an earlier spec


class ExpectedEffect(BaseModel):
    primary_metric: str                     # e.g. "leadgen_form_submit_rate"
    direction: Literal["increase", "decrease"]
    magnitude_pct: float = Field(ge=0, le=100, description="Expected lift in %")
    confidence: Literal["low", "medium", "high"]
    mde_pct: float = Field(ge=0, description="Minimum detectable effect")
    rationale: str


class EvidenceItem(BaseModel):
    kind: Literal["heuristic", "competitor_pattern", "prior_test",
                  "session_recording", "qual_research", "industry_study"]
    source_id: Optional[str] = None         # FK into reference_snapshots / learnings
    source_url: Optional[HttpUrl] = None
    excerpt: str
    weight: float = Field(ge=0, le=1)


class Evidence(BaseModel):
    items: list[EvidenceItem] = Field(min_length=1)
    aggregate_strength: Literal["weak", "moderate", "strong"]


class ChangeBlock(BaseModel):
    """Either control or variant. Free-form dict + structured anchors."""
    label: str                                # "Control" | "Variant A"
    target_zone: str                          # CSS selector or semantic role
    copy: Optional[str] = None
    asset_url: Optional[HttpUrl] = None
    style_overrides: dict[str, str] = Field(default_factory=dict)
    component_html: Optional[str] = None      # only for L4
    notes: Optional[str] = None


class Traceability(BaseModel):
    snapshot_id: str                          # FK reference_snapshots.id
    agent_run_ids: list[str] = Field(min_length=1)   # FK agent_runs.id (one per agent)
    decision_run_id: str                      # FK decision_runs.id
    proposal_id: str                          # FK agent_proposals.id
    rag_context_ids: list[str] = Field(default_factory=list)
    cost_run_id: Optional[str] = None         # FK cost_events.run_id


class ReviewEvent(BaseModel):
    at: datetime
    actor: str                                # email / handle
    action: Literal["approve", "reject", "modify", "comment", "ship"]
    note: Optional[str] = None
    diff: Optional[dict] = None               # JSON-patch for modify


class HypothesisSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Identity --------------------------------------------------------------
    hypothesis_id: str = Field(default_factory=lambda: f"hyp_{uuid.uuid4().hex[:12]}")
    schema_version: Literal["1.0.0"] = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Project context -------------------------------------------------------
    client: str
    project_id: str
    page_url: HttpUrl
    page_archetype: str                       # "lead_gen_landing", "saas_pricing", ...

    # The hypothesis -------------------------------------------------------
    title: str = Field(max_length=120)
    hypothesis_statement: str                 # "If we ___ then ___ because ___"
    target_zone: str
    change_type: str                          # free-form taxonomy tag
    change_level: ChangeLevel
    control: ChangeBlock
    variant: ChangeBlock

    # Predictions & guardrails ---------------------------------------------
    expected_effect: ExpectedEffect
    secondary_metrics: list[str] = Field(default_factory=list)
    guardrail_metrics: list[str] = Field(min_length=1)

    # Risk & complexity ----------------------------------------------------
    risk_level: RiskLevel
    implementation_complexity: Literal["low", "medium", "high"]
    estimated_dev_hours: Optional[float] = Field(default=None, ge=0)

    # Reasoning chain ------------------------------------------------------
    evidence: Evidence
    reasoning: str                            # final synthesized reasoning trace

    # Lifecycle ------------------------------------------------------------
    decision_status: DecisionStatus = DecisionStatus.pending
    superseded_by: Optional[str] = None       # hypothesis_id of replacement
    deprecation_date: Optional[date] = None
    review_history: list[ReviewEvent] = Field(default_factory=list)

    # Audit ----------------------------------------------------------------
    traceability: Traceability

    @field_validator("hypothesis_statement")
    @classmethod
    def must_be_if_then_because(cls, v: str) -> str:
        lo = v.lower()
        if not ("if" in lo and "then" in lo and "because" in lo):
            raise ValueError("hypothesis_statement must follow 'If ... then ... because ...'")
        return v
```

### 2. Markdown template (Jinja2)

```jinja
{# src/n7/templates/proposal.md.j2 #}
---
hypothesis_id: {{ spec.hypothesis_id }}
schema_version: {{ spec.schema_version }}
client: {{ spec.client }}
project_id: {{ spec.project_id }}
page_url: {{ spec.page_url }}
page_archetype: {{ spec.page_archetype }}
title: {{ spec.title | tojson }}
change_level: {{ spec.change_level.value }}
risk_level: {{ spec.risk_level.value }}
implementation_complexity: {{ spec.implementation_complexity }}
expected_lift_pct: {{ spec.expected_effect.magnitude_pct }}
primary_metric: {{ spec.expected_effect.primary_metric }}
guardrail_metrics: {{ spec.guardrail_metrics | tojson }}
decision_status: {{ spec.decision_status.value }}
created_at: {{ spec.created_at.isoformat() }}
{% if spec.superseded_by %}superseded_by: {{ spec.superseded_by }}{% endif %}
{% if spec.deprecation_date %}deprecation_date: {{ spec.deprecation_date.isoformat() }}{% endif %}
traceability:
  snapshot_id: {{ spec.traceability.snapshot_id }}
  decision_run_id: {{ spec.traceability.decision_run_id }}
  proposal_id: {{ spec.traceability.proposal_id }}
  agent_run_ids: {{ spec.traceability.agent_run_ids | tojson }}
---

# {{ spec.title }}

> **TL;DR** — {{ spec.hypothesis_statement }}
>
> Expected: **{{ spec.expected_effect.direction }} {{ spec.expected_effect.primary_metric }}
> by ~{{ spec.expected_effect.magnitude_pct }}%** ({{ spec.expected_effect.confidence }} confidence).
> Risk: **{{ spec.risk_level.value }}** · Change-level: **{{ spec.change_level.value }}**.

## Decision

To approve / reject / modify, edit the `decision_status` field in the frontmatter above.
Valid values: `approved`, `rejected`, `modified`. Any change is picked up by the watcher
within ~2 seconds.

## Control vs. Variant

### Control
- **Zone:** `{{ spec.control.target_zone }}`
{% if spec.control.copy %}- **Copy:** {{ spec.control.copy }}{% endif %}
{% if spec.control.asset_url %}- **Asset:** {{ spec.control.asset_url }}{% endif %}

### Variant
- **Zone:** `{{ spec.variant.target_zone }}`
{% if spec.variant.copy %}- **Copy:** {{ spec.variant.copy }}{% endif %}
{% if spec.variant.asset_url %}- **Asset:** {{ spec.variant.asset_url }}{% endif %}
{% if spec.variant.style_overrides %}- **Style overrides:** `{{ spec.variant.style_overrides | tojson }}`{% endif %}

## Predicted Effect

| Field | Value |
|---|---|
| Primary metric | `{{ spec.expected_effect.primary_metric }}` |
| Direction | {{ spec.expected_effect.direction }} |
| Magnitude | {{ spec.expected_effect.magnitude_pct }}% |
| Confidence | {{ spec.expected_effect.confidence }} |
| MDE | {{ spec.expected_effect.mde_pct }}% |

**Rationale:** {{ spec.expected_effect.rationale }}

## Guardrail Metrics

{% for m in spec.guardrail_metrics %}- `{{ m }}`
{% endfor %}

## Evidence ({{ spec.evidence.aggregate_strength }})

{% for e in spec.evidence.items %}
**{{ loop.index }}. {{ e.kind }}** (weight {{ e.weight }})
> {{ e.excerpt }}
{% if e.source_url %}— {{ e.source_url }}{% endif %}

{% endfor %}

## Discussion

<!-- Add comments below as bullet points: "- @you (2026-04-27): your note" -->

---

<details>
<summary>Reasoning trace (agents → decision)</summary>

{{ spec.reasoning }}

**Trace IDs**

- snapshot: `{{ spec.traceability.snapshot_id }}`
- decision_run: `{{ spec.traceability.decision_run_id }}`
- proposal: `{{ spec.traceability.proposal_id }}`
- agent_runs: {% for rid in spec.traceability.agent_run_ids %}`{{ rid }}`{% if not loop.last %}, {% endif %}{% endfor %}
</details>
```

### 3. State machine implementation

```python
# src/n7/lifecycle.py
from datetime import datetime
from statemachine import StateMachine, State
from .models import HypothesisSpec, DecisionStatus, ReviewEvent


class HypothesisLifecycle(StateMachine):
    """Source of truth for valid status transitions on a HypothesisSpec.

    Transitions are intentionally restrictive:
        pending  -> approved | rejected | modified
        modified -> approved | rejected           (modify spawns a new spec; the *old* one
                                                   gets superseded, the *new* one starts
                                                   in pending again)
        approved -> shipped | rejected            (last-mile abort allowed)
        shipped  -> (terminal; supersede via new spec)
        rejected -> (terminal; archived)
    """

    pending    = State(initial=True, value=DecisionStatus.pending.value)
    approved   = State(value=DecisionStatus.approved.value)
    rejected   = State(value=DecisionStatus.rejected.value, final=True)
    modified   = State(value=DecisionStatus.modified.value)
    shipped    = State(value=DecisionStatus.shipped.value, final=True)
    superseded = State(value=DecisionStatus.superseded.value, final=True)

    approve   = pending.to(approved)    | modified.to(approved)
    reject    = pending.to(rejected)    | approved.to(rejected) | modified.to(rejected)
    modify    = pending.to(modified)    | approved.to(modified)
    ship      = approved.to(shipped)
    supersede = (pending | approved | modified).to(superseded)

    def __init__(self, spec: HypothesisSpec):
        self.spec = spec
        super().__init__(start_value=spec.decision_status.value)

    # Hooks -----------------------------------------------------------------
    def on_transition(self, event, source, target, actor: str = "system",
                      note: str | None = None):
        self.spec.decision_status = DecisionStatus(target.value)
        self.spec.review_history.append(
            ReviewEvent(at=datetime.utcnow(), actor=actor, action=event, note=note)
        )

    def on_enter_approved(self, actor: str = "system", **_):
        # downstream: notify AssistantBriefingService → Java Assistant
        from .events import emit
        emit("hypothesis.approved", spec=self.spec, actor=actor)

    def on_enter_shipped(self, actor: str = "system", **_):
        from .events import emit
        emit("hypothesis.shipped", spec=self.spec, actor=actor)

    def on_enter_rejected(self, actor: str = "system", note: str | None = None, **_):
        from .events import emit
        emit("hypothesis.rejected", spec=self.spec, actor=actor, reason=note)
```

### 4. File watcher → status-change handler

```python
# src/n7/watcher.py
import threading, time, logging
from pathlib import Path
import frontmatter
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .models import HypothesisSpec, DecisionStatus
from .lifecycle import HypothesisLifecycle

log = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 1.5


class StatusChangeHandler(FileSystemEventHandler):
    """Watches a vault folder; on each .md file modify, debounces, re-parses,
    diffs decision_status, and triggers the corresponding lifecycle event."""

    def __init__(self, vault_root: Path, status_cache: dict[Path, str]):
        self.vault_root = vault_root
        self._cache = status_cache         # path -> last-seen status
        self._timers: dict[Path, threading.Timer] = {}
        self._last_seen: dict[Path, float] = {}

    def on_modified(self, event: FileModifiedEvent):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        path = Path(event.src_path)
        now = time.monotonic()
        # Timestamp-based debounce: only fire if >DEBOUNCE_SECONDS since last event
        last = self._last_seen.get(path, 0)
        self._last_seen[path] = now
        # Cancel any pending timer and reschedule
        if t := self._timers.get(path):
            t.cancel()
        timer = threading.Timer(DEBOUNCE_SECONDS, self._process, args=(path,))
        self._timers[path] = timer
        timer.daemon = True
        timer.start()

    def _process(self, path: Path):
        try:
            post = frontmatter.load(str(path))
            spec = HypothesisSpec.model_validate({**post.metadata,
                                                  "reasoning": "",      # body not in fm
                                                  # NB: full reload would re-read body
                                                  })  # see note below
        except Exception as e:
            log.exception("Failed to parse %s: %s", path, e)
            return

        prev = self._cache.get(path)
        curr = spec.decision_status.value
        if prev == curr:
            return

        self._cache[path] = curr

        # Map status delta to lifecycle event
        sm = HypothesisLifecycle(spec)
        # python-statemachine accepts the event name as a string-attr:
        #   sm.approve(actor=..., note=...)
        action_map = {
            DecisionStatus.approved.value: "approve",
            DecisionStatus.rejected.value: "reject",
            DecisionStatus.modified.value: "modify",
            DecisionStatus.shipped.value:  "ship",
        }
        if action := action_map.get(curr):
            try:
                getattr(sm, action)(actor="human:obsidian",
                                    note=post.metadata.get("review_note"))
            except Exception as e:
                log.error("Illegal transition %s -> %s on %s: %s",
                          prev, curr, path, e)


def start_watcher(vault_root: Path, use_polling: bool = False):
    cache: dict[Path, str] = {}
    handler = StatusChangeHandler(vault_root, cache)
    observer = PollingObserver(timeout=2.0) if use_polling else Observer()
    observer.schedule(handler, str(vault_root), recursive=True)
    observer.daemon = True
    observer.start()
    return observer
```

> **Note on body persistence:** in production we keep two on-disk artefacts per spec:
> the rendered `.md` (human-facing, owns `decision_status` + `review_note`) and a sibling
> `.spec.json` (machine-canonical, the full Pydantic dump). The watcher only re-parses
> the frontmatter from `.md`; it loads the full spec from `.spec.json` to avoid
> round-trip loss on free-form fields like `reasoning`. The `.spec.json` is regenerated
> on every Modify cycle.

### 5. Traceability lookup query

```python
# src/n7/queries.py
def fetch_full_lineage(hypothesis_id: str, conn) -> dict:
    """Single round-trip JOIN that reconstructs the full chain from
    snapshot → agents → proposal → decision → hypothesis → review history.
    Used by the audit endpoint and the Reasoning Trace renderer.
    """
    sql = """
    SELECT
        h.spec_json,
        d.formula_inputs       AS decision_inputs,
        d.formula_output       AS decision_score,
        p.proposal_json        AS proposal_payload,
        s.url, s.captured_at,
        json_agg(DISTINCT jsonb_build_object(
            'agent_id', ar.agent_id,
            'rubric_version', ar.rubric_version,
            'output', ar.output_json,
            'cost_usd', ar.cost_usd
        )) AS agent_runs,
        json_agg(DISTINCT jsonb_build_object(
            'at', rh.at, 'actor', rh.actor,
            'action', rh.action, 'note', rh.note
        )) AS review_history
    FROM hypothesis_specs h
    JOIN decision_runs    d  ON d.id = h.decision_run_id
    JOIN agent_proposals  p  ON p.id = h.proposal_id
    JOIN reference_snapshots s ON s.id = (p.proposal_json->>'snapshot_id')::bigint
    LEFT JOIN agent_runs       ar ON ar.proposal_id = p.id
    LEFT JOIN review_history   rh ON rh.hypothesis_id = h.id
    WHERE (h.spec_json->>'hypothesis_id') = %s
    GROUP BY h.spec_json, d.formula_inputs, d.formula_output,
             p.proposal_json, s.url, s.captured_at;
    """
    return conn.execute(sql, (hypothesis_id,)).fetchone()
```

### 6. Bulk approval index file (Dataview)

```markdown
# Proposals — {{ today }}

```dataview
TABLE WITHOUT ID
  file.link               AS Proposal,
  decision_status         AS Status,
  expected_lift_pct       AS "Lift %",
  risk_level              AS Risk,
  change_level            AS Level
FROM "01_Projects/{{ client }}"
WHERE schema_version = "1.0.0" AND file.name != this.file.name
SORT decision_status ASC, expected_lift_pct DESC
```
```

The reviewer opens this one file, sees all proposals as a sortable table, click-throughs
to edit `decision_status` in any individual file, and the table re-renders. Bulk approve
= "open three tabs, edit three frontmatter values, save". No custom UI required for MVP.

---

## Anti-patterns (do not do)

1. **Don't put the entire `HypothesisSpec` in YAML frontmatter.** YAML chokes on multi-line `reasoning`, escaped quotes, nested `evidence.items`. Keep frontmatter to scalars + one-level lists. Use the sibling `.spec.json` for the canonical machine state, and the Markdown body for the human-readable narrative.
2. **Don't use `transitions` (pytransitions) for an audited workflow.** Its monkey-patching makes pytype/mypy unhappy and obscures which methods exist on which class. `python-statemachine` is the better fit when reviewers will read the code.
3. **Don't trust a single watchdog event.** Saving a 5 KB Markdown file in Obsidian on Windows fires 1 Created (atomic-temp), 2-3 Modified, 1 Renamed. Always debounce; never act on the first event.
4. **Don't poll the database from the watcher.** Watcher fires a domain event; downstream subscribers (M14 adapter, M15 feedback, M9 hub) handle DB writes. Watcher's only job is parse → diff → emit.
5. **Don't delete on reject.** Move to `01_Projects/<client>/_archive/rejected/` and keep the file. Auditors and the M15 FeedbackLoopService both need rejected proposals to learn from misses.
6. **Don't mutate a shipped spec.** Modifications after ship create a new spec with `superseded_by` pointing back. dbt's model-versioning playbook is the reference.
7. **Don't conflate `modified` and `approved`.** `modified` means "human edited the spec; needs re-review" — it goes back to `pending` semantics for the new version. `approved` is a terminal-ish gate that authorizes M14.
8. **Don't use Markdown headings for status.** Headings get reformatted by Obsidian plugins, by Prettier, by the user's own habits. Status lives in *frontmatter only*. The body is descriptive prose.
9. **Don't accept LLM-generated `hypothesis_id`s.** Generate UUIDs server-side; the LLM is good at confidently inventing IDs that collide.
10. **Don't ship without a `guardrail_metrics` list of length ≥ 1.** Pydantic enforces this with `min_length=1`. A hypothesis with no guardrail is a hypothesis that can hurt revenue.

---

## Recommended starter library set

| Concern | Library | Why |
|---|---|---|
| Schema + validation | `pydantic ^2.7` | Already in stack. v2 model_config, field_validator. |
| Markdown templating | `jinja2 ^3.1` | Standard. Custom filters for date / tojson. |
| Frontmatter I/O | `python-frontmatter ^1.1` | Lossless YAML round-trip. ~120 LOC dependency. |
| State machine | `python-statemachine ^2.3` | Class-based, hooks, type-friendly. |
| File watching | `watchdog ^4.0` | Native APIs + PollingObserver fallback. |
| Event bus (intra-process) | `blinker ^1.7` *or* `pyee ^11` | Decouple `on_enter_*` from downstream subscribers. |
| Logging / tracing | `structlog ^24` | Structured events into the same log pipeline as agents. |
| Tests | `pytest ^8` + `freezegun` + `pyfakefs` | Time-travel for status timestamps; fake FS for watcher tests. |

Total new transitive deps: ~12. All MIT/BSD/Apache. No JVM, no Node.

---

## Open verifications (must answer before sprint 7)

1. **OBS-01** — Does the user's Obsidian vault sit on a sync-folder (iCloud / Dropbox / OneDrive)? If yes, force `PollingObserver` with `timeout=3.0`; native FSEvents and ReadDirectoryChangesW miss sync-driven mutations on these volumes.
2. **OBS-02** — Confirm Obsidian writes-config: "Atomic Write" (default on Windows) creates `.tmp` + rename, which fires `Created` not `Modified`. Watcher must subscribe to both.
3. **STATE-01** — Should `modify` route through a *new* `pending` (separate `hypothesis_id`, `superseded_by` link) or mutate-in-place with version bump? Recommendation: new id, supersede old. Confirm with user.
4. **REVIEW-01** — Who is allowed to approve? MVP = single-user, but review_history.actor still needs an identity source. Recommend: `git config user.email` at startup → cached in `~/.config/n7/identity.toml`.
5. **TRACE-01** — Are `agent_run_ids` always available at spec-build time? If N6 streams partial results, we may need a `traceability_pending` flag to fill in later.
6. **GROWTHBOOK-01** — Does the existing Java Assistant already speak GrowthBook REST, or does it hit GrowthBook's GUI? Mapping HypothesisSpec → GrowthBook payload depends on this.
7. **SCHEMA-01** — Lock `schema_version: "1.0.0"`. Any breaking change → bump major and add a migrator under `src/n7/migrations/`.
8. **BULK-01** — If the user wants Slack-style approve-from-mobile in v2, plan now: the `decision_status` field is a small enough surface that a `gh issue`-style CLI (`n7 approve hyp_abc123`) is a 30-LOC addition.

---

## Sources

- python-frontmatter — https://python-frontmatter.readthedocs.io/
- python-frontmatter (GitHub) — https://github.com/eyeseast/python-frontmatter
- settings-doc — https://pypi.org/project/settings-doc/ · https://github.com/radeklat/settings-doc
- mdantic (Pydantic → Markdown table) — https://github.com/Frefreak/mdantic
- RenderCV (Pydantic + Jinja2 reference impl) — https://deepwiki.com/rendercv/rendercv
- "Generating Blog Frontmatter" (Pydantic + Jinja2 walkthrough) — https://haykot.dev/blog/generating-blog-frontmatter/
- Instructor: Jinja templating proposal — https://python.useinstructor.com/blog/2024/09/19/instructor-proposal-integrating-jinja-templating/
- pytransitions — https://github.com/pytransitions/transitions
- python-statemachine — https://python-statemachine.readthedocs.io/en/latest/
- "Top 10 State Machine Frameworks for Python" — https://statemachine.events/article/Top_10_State_Machine_Frameworks_for_Python.html
- watchdog (PyPI) — https://pypi.org/project/watchdog/
- watchdog (GitHub) — https://github.com/gorakhargosh/watchdog
- watchdog issue #346 (multiple modify events) — https://github.com/gorakhargosh/watchdog/issues/346
- watchdog issue #309 (large file multiple events) — https://github.com/gorakhargosh/watchdog/issues/309
- "Mastering File System Monitoring with Watchdog" — https://developer-service.blog/mastering-file-system-monitoring-with-watchdog-in-python/
- Lazydog (event aggregation on top of watchdog) — https://lazydog.readthedocs.io/autodoc.html
- GrowthBook overview — https://docs.growthbook.io/overview
- GrowthBook experiment configuration — https://docs.growthbook.io/app/experiment-configuration
- GrowthBook metrics (goal/secondary/guardrail) — https://docs.growthbook.io/app/metrics
- GrowthBook REST API — https://docs.growthbook.io/api/
- Optimizely Variation API — https://docs.developers.optimizely.com/full-stack-experimentation/docs/optimizelyvariation
- Optimizely flag variations — https://docs.developers.optimizely.com/feature-experimentation/docs/create-flag-variations
- VWO CRO roadmap — https://vwo.com/blog/build-cro-roadmap/
- "How to Run CRO Tests the Right Way" (Mouseflow) — https://mouseflow.com/blog/cro-test/
- Conversion.com: experimentation framework — https://conversion.com/blog/build-experimentation-cro-ab-testing-framework/
- ICE scoring (Linear) — https://lineardesign.com/blog/ice-score/
- dbt model versioning — https://docs.getdbt.com/best-practices/how-we-mesh/mesh-6-coordinate-versions
- Azure soft-delete vs versioning — https://learn.microsoft.com/en-us/azure/storage/blobs/soft-delete-vs-versioning-options
- API deprecation guide (Zuplo) — https://zuplo.com/learning-center/deprecating-rest-apis
- Comet Opik thread-level human-in-the-loop — https://www.comet.com/site/blog/thread-level-human-feedback/
- Comet Opik review workflows — https://www.comet.com/site/blog/human-in-the-loop/
- LangChain human-in-the-loop docs — https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Cloudflare Agents human-in-the-loop — https://developers.cloudflare.com/agents/concepts/human-in-the-loop/
- Bulk action UX (Eleken) — https://www.eleken.co/blog-posts/bulk-actions-ux
- Complex approvals UX (UXPin) — https://www.uxpin.com/studio/blog/complex-approvals-app-design/
- GitHub frontmatter conventions — https://docs.github.com/en/contributing/writing-for-github-docs/using-yaml-frontmatter
- Yamale YAML schema validator — https://github.com/23andMe/Yamale
- "Validate YAML in Python with Schema" — https://www.andrewvillazon.com/validate-yaml-python-schema/
- Obsidian Kanban Status Updater — https://www.obsidianstats.com/plugins/kanban-status-updater
- "Markdown Kanban with Obsidian" — https://pakstech.com/blog/obsidian-kanban/
- Audit Trails for LLM Accountability (arXiv) — https://arxiv.org/html/2601.20727
