# Node N8 — Auto Feedback Loop Research

> Scope: Pull experiment FINISHED events from GrowthBook → fetch metrics + statistics (Z-test, p-value, lift) → match to local hypothesis_spec by `experiment_id` → LLM auto-summarises results vs. prediction → drafts `learning_<id>.md` in an Obsidian vault with `prediction_check`, key insights, statistical interpretation. Authority Tier 1 (highest). Solo-dev MVP, output language English.

---

## TL;DR

- **Trigger**: Use GrowthBook **Event Webhooks** (push) as the primary path with HMAC signature verification per the Standard Webhooks spec, plus a nightly cron reconciliation poll against `GET /api/v1/experiments/{id}/results` as the safety net. Webhook-only is brittle for a solo dev (missed events kill the loop); poll-only adds latency. The hybrid is two screens of code and removes a whole class of bug.
- **LLM summarisation**: Always feed the LLM a **structured stats dict + a hypothesis_spec dict + a fixed Markdown template with placeholders** — never let it freeform the whole note. Use a strict system prompt that forbids new numbers, requires `"insufficient data"` when a field is missing, and outputs JSON-with-prose fields that you splice into the template. Recent 2025 research shows structured prompts cut hallucination ~22 pp (Nature) and 33% in medical summarisation.
- **Prediction tracking**: Compute a **Brier score per hypothesis** (predicted lift direction × confidence vs. actual), persist into the hypothesis row, and roll up into a calibration curve every N tests. Use `sklearn.metrics.brier_score_loss` and `sklearn.calibration.calibration_curve`. This is the long-term "is the agent system actually learning" metric.
- **Vault git**: For an MVP, **`subprocess` wrapping `git`** beats both GitPython and dulwich. It is dependency-free, debuggable, and the failure modes match what you'd see at the CLI. Move to GitPython only when you need programmatic diff/log walking; reach for dulwich only if you have to ship without `git` on PATH.
- **Quality gate**: Every auto-drafted note ships with `status: draft`, a `confidence: low|medium|high` field derived from p-value × sample size × LLM self-rated confidence, and a `needs_review_reasons: []` list. The vault index renders red badges on low-confidence drafts. Human flips `status: approved` to ETL into the Tier-1 KB.
- **Build vs buy**: **Build** the orchestration; reuse libraries for the boring pieces (`growthbook` Python SDK for client calls, `python-frontmatter` for YAML, `subprocess`+`git` for vault, `sklearn` for calibration). No off-the-shelf product wires this whole loop for $0.

---

## Top 5 existing solutions (closest analogues)

1. **GrowthBook itself** — has experiment results + slack/discord notifications via Event Webhooks, but stops at "the test ended, here's a link". It does not write learnings back, does not check predictions, does not draft notes. We sit on top of it. (Open-source, MIT, self-hosted option.) [docs.growthbook.io/api](https://docs.growthbook.io/api/), [docs.growthbook.io/app/webhooks/event-webhooks](https://docs.growthbook.io/app/webhooks/event-webhooks).
2. **Eppo / Statsig post-experiment readouts** — closed SaaS, do auto-summarisation of stat results into prose for non-analysts. Closest paid analogue. Worth reading their public blog posts on "automated readouts" for prompt patterns; not reusable code.
3. **GoodUI Evidence library** — public CRO learning library with structured per-test cards (pattern, prediction, result, lift, confidence). Best reference for *what a finished learning note should look like*. [goodui.org/tests](https://goodui.org/tests/).
4. **Convert.com / Speero "Think Like a CRO Pro" learning logs** — shape of learning entries used by agencies; patterns documented on their blog posts for hypothesis → result → insight format.
5. **Forecast-tracking apps (PredictionBook, Metaculus)** — not CRO, but the canonical reference for *prediction calibration tracking*. Their data model (claim, probability, resolution date, resolved value, Brier) maps 1:1 to our hypothesis → outcome. [LessWrong: forecasting accuracy across horizons](https://www.lesswrong.com/posts/bXBfccjkNkc4nhLdR/data-on-forecasting-accuracy-across-different-time-horizons).

There is no off-the-shelf product that combines (a) experiment platform integration, (b) hypothesis-prediction matching, (c) LLM auto-summary, and (d) Markdown KB write-back. That gap is the whole reason N8 exists.

---

## Code references worth studying

- **`growthbook/growthbook` repo (TypeScript backend, MIT)** — `packages/back-end/src/api/experiments/` for the results payload shape; `packages/back-end/src/events/` for the webhook event taxonomy. Reading `event-types.ts` once tells you exactly which event names you should subscribe to.
- **Standard Webhooks spec** ([standardwebhooks.com](https://www.standardwebhooks.com/)) — GrowthBook follows it; same verification logic works for Stripe, Resend, and most modern senders. Lets you write one verification helper for the project.
- **`python-frontmatter` (eyeseast/python-frontmatter)** — battle-tested YAML-frontmatter loader/dumper used by Pelican, MkDocs and many Obsidian tools. ~200 stars but wide install base.
- **`scores` library** ([scores.readthedocs.io](https://scores.readthedocs.io/en/1.1.0/tutorials/Brier_Score.html)) — climate-forecasting community library with a clean Brier API and good docs explaining the score against worked examples. Even if you stick with sklearn, the docs are the best plain-English Brier explainer.
- **Obsidian vault automation case study** — Eferro's "How I use Claude Code to maintain an Obsidian vault" (2026) describes a Makefile + ~15 Python scripts pattern with `validate_frontmatter.py` as a nightly check. Lift the pattern wholesale.
- **`davidpp/obsidian-cli`** — small, AI-friendly CLI for vault ops (frontmatter get/set, search). Useful as a reference for sane vault-API surface.
- **`mathe00/obsidian-plugin-python-bridge`** — overkill for our case but documents the vault-ops surface area you might eventually want.

---

## Production case studies (if any)

- **Microsoft ExP "Patterns of Trustworthy Experimentation"** — 14+ years of experiment patterns, including post-experiment analysis and learning capture. The "Patterns" series (multiple Microsoft Research articles) is the reference for what mature learning-capture looks like at scale. Not directly reusable, but defines the bar.
- **Booking.com experimentation culture** — public talks repeatedly emphasise that *failed* tests get the same write-up rigour as winners. This is the strongest argument for auto-drafting *every* finished test, not just stat-sig wins. [VWO interview with Booking](https://vwo.com/blog/cro-best-practices-booking/).
- **Meta scaling regression adjustment** ([Analytics at Meta on Medium](https://medium.com/@AnalyticsAtMeta/how-meta-scaled-regression-adjustment-to-improve-power-across-hundreds-of-thousands-of-experiments-624e08aaf560)) — out of our MVP scope, but instructive: at scale, the bottleneck is *automated interpretation*, not raw stats. Validates the N8 thesis.
- **Nature 2025 medical-summary hallucination study** — structured prompts + source-grounding cut hallucination 33% in clinical summarisation. Same primitives apply to "summarise these stats" because both are structured-data → prose. ([Nature s41746-025-01670-7](https://www.nature.com/articles/s41746-025-01670-7), [Nature s41598-025-31075-1](https://www.nature.com/articles/s41598-025-31075-1)).

---

## Build vs buy verdict

**Build, with aggressive reuse of small libraries.** No SaaS exists for the (experiment platform → hypothesis match → LLM draft → Obsidian write-back) loop. The orchestration is 300–600 LOC of glue; the value is in the *prompt design* and the *learning schema*, neither of which a vendor can sell you.

What to *not* build:
- Don't roll your own webhook signature verification — use `standardwebhooks` Python SDK (or copy 20 lines of HMAC-SHA256).
- Don't roll your own YAML frontmatter parser — `python-frontmatter`.
- Don't roll your own Brier/calibration math — `sklearn.metrics`.
- Don't roll your own git client — `subprocess` + the `git` CLI.

What to build:
- The hypothesis ↔ experiment lookup (project-specific schema).
- The summarisation prompt + template (project-specific voice).
- The `prediction_check` logic (project-specific definition of "directional win").
- The confidence-flag heuristic (project-specific risk tolerance).

---

## Concrete patterns to copy

### 1. Experiment-finished webhook handler (FastAPI + HMAC verification)

```python
# app/webhooks/growthbook.py
import hmac, hashlib, base64, time
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.config import GROWTHBOOK_WEBHOOK_SECRET
from app.feedback.pipeline import process_experiment_finished

router = APIRouter()

MAX_SKEW_SECONDS = 5 * 60  # reject replays older than 5 min

def _verify(webhook_id: str, ts: str, body: bytes, sig_header: str) -> None:
    if abs(time.time() - int(ts)) > MAX_SKEW_SECONDS:
        raise HTTPException(401, "stale timestamp")
    signed = f"{webhook_id}.{ts}.{body.decode()}".encode()
    mac = hmac.new(GROWTHBOOK_WEBHOOK_SECRET.encode(), signed, hashlib.sha256)
    expected = "v1," + base64.b64encode(mac.digest()).decode()
    # constant-time compare
    if not hmac.compare_digest(expected, sig_header):
        raise HTTPException(401, "bad signature")

@router.post("/webhooks/growthbook")
async def growthbook(request: Request, bg: BackgroundTasks):
    body = await request.body()  # raw bytes BEFORE any parsing
    h = request.headers
    _verify(h["webhook-id"], h["webhook-timestamp"], body, h["webhook-signature"])

    event = await request.json()
    if event.get("type") != "experiment.updated":
        return {"ok": True, "skipped": event.get("type")}
    if event.get("data", {}).get("status") != "stopped":
        return {"ok": True, "skipped": "not_stopped"}

    # acknowledge fast, do work in background
    experiment_id = event["data"]["id"]
    bg.add_task(process_experiment_finished, experiment_id, event_id=h["webhook-id"])
    return {"ok": True}
```

Notes: read `request.body()` *before* anything else (FastAPI consumes the stream once); use `hmac.compare_digest` (timing-attack safe); idempotency-key the downstream task by `webhook-id` so retries don't double-write.

### 2. GrowthBook stats fetch + interpretation prompt

```python
# app/feedback/pipeline.py
import httpx
from app.config import GROWTHBOOK_API_KEY, GROWTHBOOK_BASE_URL
from app.feedback.summariser import draft_learning
from app.feedback.vault import write_learning_note
from app.db import get_hypothesis_by_experiment_id, save_learning

async def fetch_results(experiment_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{GROWTHBOOK_BASE_URL}/api/v1/experiments/{experiment_id}/results",
            headers={"Authorization": f"Bearer {GROWTHBOOK_API_KEY}"},
        )
        r.raise_for_status()
        return r.json()

async def process_experiment_finished(experiment_id: str, event_id: str) -> None:
    results = await fetch_results(experiment_id)
    hypothesis = get_hypothesis_by_experiment_id(experiment_id)
    if not hypothesis:
        # Tier 1 source has no matching local hypothesis → log + skip
        return

    draft = await draft_learning(hypothesis=hypothesis, results=results)
    learning_id = save_learning(draft)  # status='draft'
    write_learning_note(learning_id, draft)  # commit to vault
```

The summarisation prompt — the load-bearing piece — looks like this:

```python
# app/feedback/summariser.py
SYSTEM = """You are a CRO analyst writing a post-experiment learning note.
You will receive a HYPOTHESIS (what we predicted, with rationale) and RESULTS (raw stats).
Rules — non-negotiable:
1. Do NOT introduce numbers that are not in RESULTS. Quote them verbatim.
2. If a field you need is missing, write the literal string "insufficient data".
3. Keep prose under 120 words per section.
4. Do not claim causation beyond what the stats support.
5. Output VALID JSON matching the provided schema. No prose outside JSON.

Statistical interpretation guide:
- p < 0.05 with N >= 1000 per arm: call it "real" (use word "evidence")
- 0.05 <= p < 0.15: call it "directional, not conclusive"
- p >= 0.15: call it "noise"
- Always mention the 95% confidence interval if present.
- Lift direction matters even when not significant: report it.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["prediction_check", "key_insights", "statistical_interpretation",
                 "confidence_self_rating", "needs_review_reasons"],
    "properties": {
        "prediction_check": {  # did we predict the right direction?
            "type": "object",
            "required": ["predicted_direction", "actual_direction", "match", "delta_vs_predicted_lift"],
        },
        "key_insights": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "statistical_interpretation": {"type": "string"},
        "confidence_self_rating": {"enum": ["low", "medium", "high"]},
        "needs_review_reasons": {"type": "array", "items": {"type": "string"}},
    },
}

async def draft_learning(hypothesis: dict, results: dict) -> dict:
    user_msg = {
        "HYPOTHESIS": hypothesis,            # includes predicted_direction, predicted_lift, rationale
        "RESULTS": _slim(results),           # only the fields we need; smaller = less drift
        "OUTPUT_SCHEMA": OUTPUT_SCHEMA,
    }
    return await llm_call(system=SYSTEM, user=user_msg, response_format="json_schema",
                          schema=OUTPUT_SCHEMA, temperature=0.2)

def _slim(results: dict) -> dict:
    # Keep only what the prompt actually uses. Pre-trim to control token budget
    # AND to control surface area for hallucination.
    metrics = []
    for m in results.get("metrics", []):
        metrics.append({
            "name": m["name"],
            "lift_pct": m.get("relativeLift"),
            "ci95": m.get("confidenceInterval"),
            "p_value": m.get("pValue"),
            "sample_size_a": m.get("usersA"),
            "sample_size_b": m.get("usersB"),
            "primary": m.get("primary", False),
        })
    return {"experiment_id": results["id"], "duration_days": results.get("durationDays"),
            "metrics": metrics}
```

Why this works: the model is given a *fixed JSON schema*, it cannot hallucinate prose into the wrong slot, and the `_slim` step strips everything that isn't load-bearing. The "statistical interpretation guide" inside the system prompt is the lever for question 6 (LLM ↔ p-value) — small, explicit rules outperform "use your judgement."

### 3. Learning note Markdown template (composed from JSON, not generated)

```python
# app/feedback/vault.py
import frontmatter
from pathlib import Path
from datetime import datetime, timezone

VAULT = Path("/srv/vault/05_Learnings")

TEMPLATE = """\
## Hypothesis
{hypothesis_summary}

## Prediction
- Direction: **{predicted_direction}**
- Expected lift: **{predicted_lift_pct:+.2f}%**
- Rationale: {predicted_rationale}

## Result
- Direction: **{actual_direction}**
- Observed lift (primary): **{actual_lift_pct:+.2f}%** (95% CI {ci_low:+.2f}% / {ci_high:+.2f}%)
- p-value: **{p_value:.4f}**, N(A)={n_a:,}  N(B)={n_b:,}
- Duration: {duration_days} days

## Prediction check
- Match: **{match}**
- Δ vs. predicted lift: **{delta_vs_predicted_lift:+.2f} pp**

## Statistical interpretation
{statistical_interpretation}

## Key insights
{key_insights_md}

## Needs review
{needs_review_md}
"""

def write_learning_note(learning_id: str, draft: dict) -> Path:
    fm = {
        "id": learning_id,
        "experiment_id": draft["experiment_id"],
        "hypothesis_id": draft["hypothesis_id"],
        "status": "draft",                       # human flips to "approved"
        "tier": 1,
        "authority": "tier-1-experiment",
        "confidence": draft["confidence_self_rating"],
        "needs_review_reasons": draft["needs_review_reasons"],
        "predicted_direction": draft["prediction_check"]["predicted_direction"],
        "actual_direction": draft["prediction_check"]["actual_direction"],
        "prediction_match": draft["prediction_check"]["match"],
        "p_value": draft["primary_metric"]["p_value"],
        "lift_pct": draft["primary_metric"]["lift_pct"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tags": ["learning", "tier-1", draft["hypothesis_pattern"]],
    }
    body = TEMPLATE.format(**draft["render_ctx"])
    post = frontmatter.Post(content=body, **fm)
    path = VAULT / f"learning_{learning_id}.md"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path
```

The template is *deterministic*. The LLM only fills typed slots (`statistical_interpretation`, `key_insights`, `needs_review_reasons`); everything else is mechanical from the stats payload. This is the single biggest hallucination control.

### 4. Vault git auto-commit pattern (subprocess)

```python
# app/feedback/git_vault.py
import subprocess
from pathlib import Path

VAULT = Path("/srv/vault")

def _run(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(VAULT), *args],
                                   text=True, stderr=subprocess.STDOUT)

def commit_and_push(file_path: Path, learning_id: str, experiment_id: str) -> str:
    rel = file_path.relative_to(VAULT)
    _run("add", str(rel))
    # status check — skip empty commits when content unchanged
    if not _run("status", "--porcelain", str(rel)).strip():
        return "noop"
    msg = (
        f"learning: draft {learning_id} from experiment {experiment_id}\n\n"
        f"Auto-generated by N8 feedback loop. Status: draft (awaiting human review).\n"
        f"Source: GrowthBook experiment {experiment_id}"
    )
    _run("commit", "-m", msg, "--author=N8 Feedback Bot <bot@local>")
    try:
        _run("push", "origin", "HEAD")
    except subprocess.CalledProcessError as e:
        # log + retry async; do NOT fail the webhook for push errors
        return f"push_deferred:{e.output[:200]}"
    return "pushed"
```

Why subprocess over GitPython/dulwich for an MVP:
- Zero new dependencies (`git` is already on the box).
- Failure modes are exactly what you'd see in a terminal — logs are greppable.
- GitPython adds 70 MB of import surface and famously leaks file handles on Windows.
- dulwich is excellent if you can't ship `git` (e.g. Lambda) but it's slower for everyday ops and the API is unfamiliar.
- Move to GitPython only when you start needing programmatic diff/log/blame walking; you don't yet.

### 5. `prediction_check` logic + Brier scoring

```python
# app/feedback/prediction_check.py
from sklearn.metrics import brier_score_loss

def check_prediction(hypothesis: dict, results: dict) -> dict:
    primary = next(m for m in results["metrics"] if m.get("primary"))
    actual_lift = primary["relativeLift"] or 0.0
    actual_dir = "up" if actual_lift > 0 else ("down" if actual_lift < 0 else "flat")
    predicted_dir = hypothesis["predicted_direction"]   # 'up' | 'down'
    predicted_lift = hypothesis["predicted_lift_pct"]   # e.g. 5.0
    predicted_conf = hypothesis["confidence"]           # 0.0..1.0 (P(direction correct))

    match = (predicted_dir == actual_dir)
    return {
        "predicted_direction": predicted_dir,
        "actual_direction": actual_dir,
        "match": match,
        "delta_vs_predicted_lift": (actual_lift - predicted_lift),
        "predicted_confidence": predicted_conf,
        "outcome_for_brier": 1 if match else 0,   # for later aggregation
    }

def system_calibration(history: list[dict]) -> dict:
    """Aggregate every resolved hypothesis into a Brier score + calibration buckets."""
    y_true  = [h["outcome_for_brier"]   for h in history]
    y_prob  = [h["predicted_confidence"] for h in history]
    return {
        "n": len(history),
        "brier_score": brier_score_loss(y_true, y_prob),
        # buckets for the calibration plot
        "calibration": _bucket(y_true, y_prob, n_bins=10),
    }
```

Run `system_calibration` weekly, write a meta-learning note `meta_calibration_<week>.md` into the vault. After 30+ resolved hypotheses you get a meaningful signal on whether the agent system is overconfident (the most common failure mode per PredictionBook data).

### 6. Confidence-flag heuristic (the "draft might be wrong" signal)

```python
# app/feedback/quality_gate.py
def confidence_and_flags(results: dict, llm_self: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    primary = next(m for m in results["metrics"] if m.get("primary"))
    p = primary.get("pValue")
    n_min = min(primary.get("usersA", 0), primary.get("usersB", 0))

    if p is None:
        flags.append("missing_p_value")
    if n_min < 200:
        flags.append("very_small_sample")
    if results.get("durationDays", 0) < 7:
        flags.append("ran_under_a_week")
    if any(m.get("srm_pvalue", 1) < 0.001 for m in results["metrics"]):
        flags.append("sample_ratio_mismatch")
    if llm_self == "low":
        flags.append("llm_low_confidence")

    # Final confidence: worst of (LLM self-rating, stats-derived)
    stats_band = "high" if (p is not None and p < 0.05 and n_min >= 1000) else \
                 "low"  if (p is None or p > 0.2 or n_min < 200) else "medium"
    final = min([llm_self, stats_band], key=lambda x: ["low", "medium", "high"].index(x))
    return final, flags
```

This is what populates the `confidence` and `needs_review_reasons` frontmatter. The vault index template renders red badges where `confidence: low` or `needs_review_reasons` is non-empty — humans see what to look at first.

---

## Anti-patterns

- **Letting the LLM freeform the entire note.** It will invent metric names, fabricate sample sizes, and confidently misread CI direction. Always template the structure, slot only prose.
- **Webhook-only with no reconciliation.** GrowthBook retries 3× then gives up; a single deploy during that window silently drops the test. Always have a nightly poll that finds `status=stopped` experiments without a corresponding `learning_*.md`.
- **Synchronous LLM call in the webhook handler.** Webhook senders time out at 5–10 s; LLM calls take 10–30 s. Always ack fast, work in background.
- **Auto-publishing learnings as Tier 1 KB.** `status: draft` → human review → `status: approved` → ETL is non-negotiable. The whole point of Tier 1 is human-vetted.
- **Skipping failed/null tests.** Booking.com publicly cites *failed* tests as their highest-leverage learning source. Draft a learning note for *every* finished test, not just stat-sig wins.
- **Storing the LLM prose in the DB and the Markdown both.** Pick one source of truth. The vault Markdown should be canonical for prose; DB stores structured fields + a pointer to the Markdown path. Bidirectional sync conflicts are not worth it for a solo dev.
- **Treating LLM `confidence_self_rating` as load-bearing alone.** Self-reported confidence calibrates moderately well but is gameable; combine with stats-derived confidence (sample size + p-value) and take the minimum.
- **Custom git commit author = system user with shell write access.** The bot account that pushes to the vault should be a deploy key with write-only access to the vault repo, *not* a general SSH user.
- **Verifying webhook signature *after* parsing JSON.** FastAPI's `request.json()` consumes the body; you'll be unable to recompute the HMAC. Read `await request.body()` first.
- **No idempotency key on the background task.** GrowthBook retries on non-200; without `webhook-id` dedupe you'll write duplicate learning notes on every retry.

---

## Recommended starter library set

| Concern | Library | Why |
|---|---|---|
| HTTP server / webhook | **FastAPI + uvicorn** | Async, dead-simple background tasks, well-known. |
| Webhook signature | **`standardwebhooks`** (or 20-line HMAC helper) | GrowthBook follows the spec; reusable for Stripe etc. |
| GrowthBook client | **`httpx`** + raw REST (skip the official `growthbook` Python SDK — that's the *runtime evaluator*, not the management API) | Management API is only documented in REST; SDK is for serving feature flags. |
| YAML frontmatter | **`python-frontmatter`** | Battle-tested, no fancy footguns. |
| Vault git ops | **`subprocess` + system `git`** | Cheapest, most debuggable for MVP. Upgrade to `GitPython` only when you need diff/log walking. |
| Stats / calibration | **`scikit-learn`** (`brier_score_loss`, `calibration_curve`) | Already a dep if you do anything ML-ish; standard API. |
| LLM client | **whichever you're using** (Anthropic / OpenAI) with **structured outputs / JSON schema mode** | Hard-enforces the output schema; biggest single hallucination cut. |
| Job queue (when MVP outgrows BackgroundTasks) | **`arq`** or **`rq`** + Redis | Both are tiny; avoid Celery for solo-dev MVP. |
| Cron / poll | **`apscheduler`** in-process, or a `cron` line | Keep it boring. |
| Schema validation | **`pydantic` v2** | Validate webhook payload + LLM JSON output. |

Avoid for MVP: Celery, Airflow, OpenLineage, dbt-OSMOSIS, custom CRDT sync. Each is a 2-week tangent.

---

## Open verifications

Things to confirm before locking the design:

1. **GrowthBook event taxonomy** — confirm exact event name for "experiment finished". Docs reference `experiment.updated` with a state field; the `experiment.warning`, `experiment.info.significance` events also fire on auto-decisions and may be a *better* trigger than the generic `updated`. Verify in `event-types.ts` of the GrowthBook repo for your installed version.
2. **`/experiments/{id}/results` payload** — exact field names for `pValue`, `relativeLift`, `confidenceInterval`, `usersA/B`, SRM `p-value`, and the `primary` flag. The official API page didn't render full schemas in search; hit your own GrowthBook instance with `curl` once and pin the field names in `_slim()`.
3. **Webhook signature scheme version** — older GrowthBook versions used a different header (`X-GrowthBook-Signature`), newer ones use Standard Webhooks (`webhook-id` / `webhook-timestamp` / `webhook-signature`). Confirm your version.
4. **`hypothesis_id` ↔ `experiment_id` link mechanism** — does GrowthBook let you stash an arbitrary key (e.g. via tags or description), or do we need a side table? Tags are the lightest path; confirm tag write/read via the API.
5. **Multi-variant experiments (A/B/n)** — N8 spec implies binary; the schema needs an `arms: [{name, lift, ci, p}]` array if you ever run >2 variants. Decide now whether to fail-loudly or auto-collapse to "best variant".
6. **LLM cost ceiling per experiment** — set a hard token budget for the summarisation call (the schema-constrained prompt is small, but `_slim()` could explode on tests with 30+ secondary metrics; cap at top 5 by absolute lift).
7. **Vault repo permissions** — is the vault a private GitHub repo, a self-hosted Gitea, or local-only? Determines push auth (deploy key vs. PAT vs. nothing).
8. **When to compute meta-calibration** — every N=10 resolved hypotheses, weekly, monthly? Pick a cadence; recommend weekly with a "skip if no new resolutions this week" guard.
9. **Failure mode on `hypothesis_id` not found** — silent skip vs. draft an "orphan learning" note? Recommend the latter so we never lose Tier 1 data; flag with `needs_review_reasons: ["unmatched_hypothesis"]`.
10. **Conflict policy if a human edits a draft, then a re-run wants to update** — recommend: never auto-overwrite a `status: draft` note that has been modified since auto-creation; instead drop a `learning_<id>.rev2.md` next to it. Solo-dev friendly, no merge logic.

---

## Sources

- [GrowthBook REST API docs](https://docs.growthbook.io/api/)
- [GrowthBook Event Webhooks](https://docs.growthbook.io/app/webhooks/event-webhooks)
- [GrowthBook SDK Webhooks (signature spec)](https://docs.growthbook.io/app/webhooks/sdk-webhooks)
- [GrowthBook Understanding Experiment Results](https://docs.growthbook.io/app/experiment-results)
- [GrowthBook open-source repo](https://github.com/growthbook/growthbook)
- [Standard Webhooks specification](https://www.standardwebhooks.com/)
- [Receive Webhooks with Python (FastAPI) — Svix](https://www.svix.com/guides/receiving/receive-webhooks-with-python-fastapi/)
- [A Practical Guide to Safely Implementing Webhook Receiver APIs in FastAPI](https://blog.greeden.me/en/2026/04/07/a-practical-guide-to-safely-implementing-webhook-receiver-apis-in-fastapi-from-signature-verification-and-retry-handling-to-idempotency-and-asynchronous-processing/)
- [Polling vs webhooks: when to use one over the other — Merge.dev](https://www.merge.dev/blog/webhooks-vs-polling)
- [Hookdeck — When to Use Webhooks, WebSocket, Pub/Sub, and Polling](https://hookdeck.com/webhooks/guides/when-to-use-webhooks)
- [GitPython tutorial](https://gitpython.readthedocs.io/en/stable/tutorial.html)
- [Dulwich — Pure-Python Git](https://www.dulwich.io/) and [Git book — Embedding Git: Dulwich](https://git-scm.com/book/en/v2/Appendix-B:-Embedding-Git-in-your-Applications-Dulwich)
- [scikit-learn `brier_score_loss`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html)
- [`scores` library — Brier Score tutorial](https://scores.readthedocs.io/en/1.1.0/tutorials/Brier_Score.html)
- [Neptune.ai — Brier Score and Model Calibration](https://neptune.ai/blog/brier-score-and-model-calibration)
- [LessWrong — Forecasting accuracy across time horizons](https://www.lesswrong.com/posts/bXBfccjkNkc4nhLdR/data-on-forecasting-accuracy-across-different-time-horizons)
- [Nature 2025 — Hallucination detection and mitigation framework for faithful text summarisation](https://www.nature.com/articles/s41598-025-31075-1)
- [Nature 2025 — npj Digital Medicine: clinical safety / hallucination rates of LLMs for summarisation](https://www.nature.com/articles/s41746-025-01670-7)
- [Frontiers 2025 — Prompt engineering for accurate statistical reasoning with LLMs in medical research](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1658316/full)
- [Microsoft Research — Patterns of Trustworthy Experimentation: Pre-Experiment Stage](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/patterns-of-trustworthy-experimentation-pre-experiment-stage/)
- [VWO — Inside Booking.com's Experimentation & CRO Culture](https://vwo.com/blog/cro-best-practices-booking/)
- [Analytics at Meta — How Meta scaled regression adjustment](https://medium.com/@AnalyticsAtMeta/how-meta-scaled-regression-adjustment-to-improve-power-across-hundreds-of-thousands-of-experiments-624e08aaf560)
- [Convert.com — Meta-Analysis in A/B Testing](https://www.convert.com/blog/a-b-testing/what-is-meta-analysis-in-ab-testing/)
- [GoodUI — A/B tested patterns library](https://goodui.org/) and [GoodUI Tests](https://goodui.org/tests/)
- [A Collaborative Template for A/B Tests — Harlan Harris](https://medium.com/@HarlanH/a-collaborative-template-for-a-b-tests-8630e41971ac)
- [arxiv 2025 — When Can We Trust LLM Graders? Calibrating Confidence for Automated Assessment](https://arxiv.org/html/2603.29559)
- [Evidently AI — LLM-as-a-judge guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Eferro — How I use Claude Code to maintain an Obsidian vault](https://www.eferro.net/2026/04/how-i-use-claude-code-to-maintain.html)
- [davidpp/obsidian-cli — Obsidian vault CLI](https://github.com/davidpp/obsidian-cli)
- [mathe00/obsidian-plugin-python-bridge — Python in Obsidian](https://github.com/mathe00/obsidian-plugin-python-bridge)
- [DZone — Conflict Resolution: Last-Write-Wins vs. CRDTs](https://dzone.com/articles/conflict-resolution-using-last-write-wins-vs-crdts)
- [OpenLineage — open standard for lineage events](https://openlineage.io/)
