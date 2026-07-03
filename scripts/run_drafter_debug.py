#!/usr/bin/env python
"""
Drafter Debug Benchmark -- 5 models x 2 prompt versions.

Purpose: capture the RAW JSON each model produces and show the EXACT
Pydantic validation error (field path + message) so we can diagnose
why certain models fail MarketingContext validation.

Lessons from round-1 run:
  - v1 prompt says "Pydantic schema" without "JSON" -> gpt-4o-mini wrote Python code!
  - Claude follows the _BRIEF_PROMPT reasoning checklist verbatim (chain-of-thought
    before JSON), so raw text starts with "I'll work through the reasoning..." ->
    json.loads fails at char 0 (not empty, just non-JSON at position 0)
  - Claude's MarketingContext JSON alone exceeds 4096 tokens -> string truncated
  - v2 prompt was missing: location_context, severity/frequency enum values

Fixes in this version:
  - Extract JSON by finding first '{' in response (skips any preamble text)
  - max_tokens=8192 (Claude MarketingContext ~5000-6000 tokens)
  - v2 prompt: complete field spec including location_context + all enum values
  - v2 prompt explicitly says "start response with {" to prevent preamble

Usage:
    python scripts/run_drafter_debug.py

Output:
    Console  -- pass/fail + specific validator errors per combo
    logs/drafter_debug_<ts>.log -- full raw responses for every call
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import openai
from pydantic import ValidationError

from ai_agent_system.config import settings
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.drafter import SYSTEM_PROMPT, _BRIEF_PROMPT

# -- Logging setup -------------------------------------------------------------

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"drafter_debug_{RUN_TS}.log"

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler])
log = logging.getLogger("drafter_debug")


# -- Models to test ------------------------------------------------------------

MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "deepseek/deepseek-chat",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-opus-4",
]

# -- Prompt v1: current production SYSTEM_PROMPT (imported from drafter.py) ---
# Known issue: says "Pydantic schema" not "output JSON" -- some models write Python.
# Also: _BRIEF_PROMPT has a reasoning checklist that Claude follows verbatim
# as preamble text before the JSON, which breaks raw JSON extraction.
PROMPT_V1 = SYSTEM_PROMPT


# -- Prompt v2: schema-first, output-only -------------------------------------
# Key differences vs v1:
#   - Explicitly says "OUTPUT ONLY THE JSON" and "Start your response with {"
#   - No reasoning checklist in user prompt (avoids chain-of-thought preamble)
#   - Complete field spec with all enum values and required/optional markers
#   - Includes location_context (was missing from earlier v2 draft)
#   - Explicit enum values for severity and frequency in pain_points

PROMPT_V2 = (
    "You are a performance-marketing strategist. Output a single JSON object\n"
    "matching the MarketingContext schema below.\n"
    "OUTPUT ONLY THE JSON -- no markdown fences, no chain-of-thought,\n"
    "no preamble, no explanation. Start your response with '{'.\n"
    "\n"
    "=== COMPLETE FIELD SPEC (every field required unless marked optional) ===\n"
    "\n"
    "Top-level (include ALL of these in the output JSON):\n"
    "  schema_version        integer, always 1\n"
    "  niche                 string (copy from metadata)\n"
    "  parent_category       string (copy from metadata)\n"
    "  market                string e.g. \"US-FL\"\n"
    "  language              \"en\" or \"en-US\" (2-letter ISO, lowercase, region uppercase)\n"
    "  traffic_source_primary  string (copy from metadata)\n"
    "  page_goal             zip_submit | phone_call | lead_form | quiz_complete | book_demo | signup\n"
    "  primary_metric        string (copy from metadata)\n"
    "  guardrail_metrics     list[string] ([] is fine)\n"
    "  source_brief          string (copy the brief text verbatim)\n"
    "\n"
    "personas -- array EXACTLY 3-5 objects, each with:\n"
    "  name              niche-specific label e.g. \"Florida Helen, 72, fall-risk widow\"\n"
    "                    FORBIDDEN: generic names like \"John, 35, marketing manager\"\n"
    "  role              primary_buyer | influencer | decision_helper | blocker\n"
    "  age_range         \"65-80\" or \"65+\" format ONLY (digits-digits or digits+)\n"
    "  location_context  geo + life stage e.g. \"Florida retiree, owns home outright\"\n"
    "  income_band       under_30k | 30_60k | 60_100k | 100_200k | over_200k | unknown\n"
    "  digital_literacy  low | medium | high\n"
    "  primary_job       JTBD: \"When [X], I want to [Y], so I can [Z].\"\n"
    "  pain_points       array min 2 max 6, each:\n"
    "    label                  string 3-7 words\n"
    "    description            concrete observable trigger (NO platitudes like \"better life\")\n"
    "    severity               low | medium | high | critical\n"
    "    frequency              one_time | occasional | frequent | constant\n"
    "    addressable_by_offer   true | false\n"
    "  trust_needs         array[string] min 2 max 5\n"
    "  decision_triggers   array[string] min 2 max 5\n"
    "  objections          array[string] min 1 max 5\n"
    "  channel_behavior    string -- device, scroll speed, time of day\n"
    "\n"
    "  WARNING: For 55+ niches you MUST include at least 1 persona with\n"
    "  role=\"decision_helper\" (adult child, spouse, or caregiver).\n"
    "\n"
    "pain_points_aggregate -- array min 3, same structure as persona pain_points\n"
    "\n"
    "user_flow:\n"
    "  stages (min 3 max 7), each:\n"
    "    stage             awareness | consideration | evaluation | intent | action | post_action\n"
    "    description       string\n"
    "    typical_duration  e.g. \"5 sec\" or \"2 days\"\n"
    "    user_question     string\n"
    "    page_must_answer  string\n"
    "  primary_friction_point  string\n"
    "  drop_off_hypothesis     string\n"
    "\n"
    "audience_profile:\n"
    "  primary_persona_name      EXACT character-for-character copy of one personas[].name\n"
    "  secondary_persona_names   array[string] ([] is fine)\n"
    "  estimated_primary_share   float 0.0-1.0\n"
    "  market                    string e.g. \"US-FL\"\n"
    "  language                  string e.g. \"en\"\n"
    "\n"
    "channel_profile -- discriminated by \"channel\" field:\n"
    "  CRITICAL: channel_profile.channel MUST be identical to traffic_source_primary\n"
    "\n"
    "  For meta:\n"
    "    { \"channel\": \"meta\",\n"
    "      \"primary_placement\": \"feed\" | \"stories\" | \"reels\" | \"marketplace\",\n"
    "      \"typical_mindset\": string,\n"
    "      \"creative_format_pref\": [\"static_image\"|\"carousel\"|\"video_15s\"|\"video_30s\"|\"ugc_style\"],\n"
    "      \"age_targeting_note\": string | null }\n"
    "\n"
    "  For google_search:\n"
    "    { \"channel\": \"google_search\",\n"
    "      \"intent_level\": \"informational\" | \"commercial\" | \"transactional\",\n"
    "      \"typical_query_examples\": [string, string ...] (min 2),\n"
    "      \"competitor_density\": \"low\" | \"medium\" | \"high\" | \"saturated\" }\n"
    "\n"
    "=== END SPEC ===\n"
    "\n"
    "<retrieved_context>\n"
    "No prior knowledge found. Produce a conservative draft.\n"
    "</retrieved_context>\n"
)

# -- Test case: homeiq.io / walk-in tubs / FL seniors / meta ------------------

TEST_BRIEF = (
    "HomeIQ sells walk-in tubs and bath safety solutions for seniors. "
    "Target: 65+ adults in Florida who fear falling in the shower or tub, "
    "plus adult children helping aging parents make home-safety decisions. "
    "Traffic: Meta (Facebook / Instagram) paid ads. "
    "Goal: ZIP code submission so a local installer can follow up. "
    "Offer: Free in-home assessment, no high-pressure sales, veteran discounts."
)

TEST_META = dict(
    niche="walk_in_tubs",
    parent_category="home_safety",
    market="US-FL",
    language="en",
    traffic_source_primary="meta",
    page_goal="zip_submit",
    primary_metric="zip_submit_rate",
    brief=TEST_BRIEF,
    business_constraints=(
        "Special Ad Category: housing -- age/ZIP targeting blocked for US audiences"
    ),
)


def _build_user_prompt_v1() -> str:
    """v1 uses the production _BRIEF_PROMPT but appends a JSON-only instruction."""
    base = _BRIEF_PROMPT.format(
        brief=TEST_META["brief"],
        niche=TEST_META["niche"],
        parent_category=TEST_META["parent_category"],
        market=TEST_META["market"],
        language=TEST_META["language"],
        traffic_source_primary=TEST_META["traffic_source_primary"],
        page_goal=TEST_META["page_goal"],
        primary_metric=TEST_META["primary_metric"],
        constraints_line=f"- business_constraints: {TEST_META['business_constraints']}",
    )
    # Fix: append explicit JSON-only instruction so models don't write Python
    return base + "\n\nIMPORTANT: Output ONLY raw JSON. No code, no explanation, no markdown."


def _build_user_prompt_v2() -> str:
    """v2 uses a minimal prompt -- the schema spec is already in the system prompt."""
    return (
        f"Niche: {TEST_META['niche']}\n"
        f"Parent category: {TEST_META['parent_category']}\n"
        f"Market: {TEST_META['market']}\n"
        f"Language: {TEST_META['language']}\n"
        f"Traffic source: {TEST_META['traffic_source_primary']}\n"
        f"Page goal: {TEST_META['page_goal']}\n"
        f"Primary metric: {TEST_META['primary_metric']}\n"
        f"Constraints: {TEST_META['business_constraints']}\n"
        f"\nBrief:\n{TEST_META['brief']}\n"
        f"\nGenerate the MarketingContext JSON now. Start your response with '{{'."
    )


# -- JSON extraction helpers ---------------------------------------------------

def _extract_json(raw: str) -> str:
    """
    Extract the first JSON object from an arbitrary string.
    Handles:
      - Clean JSON response (starts with '{')
      - Markdown-fenced response (```json ... ```)
      - Response with prose preamble (e.g. "Here is the JSON:\n{...}")
      - Response with chain-of-thought before JSON
    """
    raw = raw.strip()

    # Case 1: markdown fence -- extract content between first ``` pair
    if "```" in raw:
        lines = raw.splitlines()
        inside = False
        json_lines: list[str] = []
        for line in lines:
            if line.startswith("```"):
                inside = not inside
                continue
            if inside:
                json_lines.append(line)
        candidate = "\n".join(json_lines).strip()
        if candidate.startswith("{"):
            return candidate

    # Case 2: find first '{' -- skips any preamble text
    first_brace = raw.find("{")
    if first_brace >= 0:
        return raw[first_brace:]

    # Case 3: give up -- return as-is (json.loads will fail with a clear error)
    return raw


# -- Single-combo runner -------------------------------------------------------

async def run_one(
    model: str,
    pv: int,
    client: openai.AsyncOpenAI,
) -> dict:
    """
    Make one raw API call, extract + validate JSON, return a result dict.
    No pydantic-ai involved -- we want to see raw output before any retry magic.
    """
    if pv == 1:
        system_prompt = PROMPT_V1 + (
            "\n\n<retrieved_context>\n"
            "No prior knowledge found. Produce a conservative draft.\n"
            "</retrieved_context>"
        )
        user_prompt = _build_user_prompt_v1()
    else:
        system_prompt = PROMPT_V2
        user_prompt = _build_user_prompt_v2()

    log.info("\n" + "=" * 70)
    log.info("MODEL=%s  PROMPT=v%d", model, pv)
    log.debug("SYSTEM:\n%s", system_prompt[:800])
    log.debug("USER:\n%s", user_prompt)

    result: dict = dict(
        model=model,
        pv=pv,
        success=False,
        latency_s=0.0,
        raw_text=None,
        json_ok=False,
        val_ok=False,
        errors=[],
        api_error=None,
    )

    t0 = time.time()
    try:
        call_kwargs: dict = dict(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=8192,   # Claude MarketingContext ~5-6k tokens -- 4096 was truncating
        )

        try:
            resp = await client.chat.completions.create(
                **call_kwargs,
                response_format={"type": "json_object"},
                timeout=240,
            )
        except openai.BadRequestError as e:
            log.warning("json_object mode rejected (code=%s), retrying without it", e.code)
            resp = await client.chat.completions.create(
                **call_kwargs,
                timeout=240,
            )

        result["latency_s"] = round(time.time() - t0, 1)
        raw = (resp.choices[0].message.content or "").strip()
        result["raw_text"] = raw
        log.info("RAW RESPONSE (%d chars):\n%s", len(raw), raw[:3000])
        if len(raw) > 3000:
            log.info("... (truncated in log -- full response is %d chars)", len(raw))

        # -- JSON extraction (handles preamble text and markdown fences) -------
        extracted = _extract_json(raw)

        try:
            data = json.loads(extracted)
        except json.JSONDecodeError as e:
            result["api_error"] = f"JSON parse failed: {e}"
            log.warning("JSON parse error after extraction: %s", e)
            log.debug("Extracted candidate (first 500 chars): %s", extracted[:500])
            return result

        result["json_ok"] = True

        # -- Pydantic validation -----------------------------------------------
        try:
            MarketingContext.model_validate(data)
            result["val_ok"] = True
            result["success"] = True
            log.info("VALIDATION: PASSED")
        except ValidationError as ve:
            errs = ve.errors(include_url=False)
            result["errors"] = [
                {
                    "loc": " -> ".join(str(x) for x in e["loc"]),
                    "msg": e["msg"],
                    "type": e["type"],
                }
                for e in errs
            ]
            log.warning(
                "VALIDATION FAILED (%d errors):\n%s",
                len(errs),
                json.dumps(result["errors"], indent=2),
            )

    except openai.APIError as e:
        result["latency_s"] = round(time.time() - t0, 1)
        result["api_error"] = str(e)
        log.error("API error: %s", e)

    return result


# -- Main ----------------------------------------------------------------------

async def main() -> None:
    client = openai.AsyncOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
        default_headers={
            "HTTP-Referer": "https://github.com/ai-agent-system",
            "X-Title": "AI Agent System Drafter Debug",
        },
    )

    combos = [(m, pv) for m in MODELS for pv in (1, 2)]
    results: list[dict] = []

    W = 80
    print("=" * W)
    print(f"  DRAFTER DEBUG r2  |  {len(combos)} combos  |  log -> logs/{LOG_FILE.name}")
    print("=" * W)

    for model, pv in combos:
        short = model.split("/")[-1]
        label = f"{short} | prompt-v{pv}"
        print(f"\n  {label:<52}", end=" ", flush=True)

        r = await run_one(model, pv, client)
        results.append(r)

        if r["success"]:
            print(f"OK  ({r['latency_s']}s)")
        elif r["api_error"]:
            print(f"API-ERR  ({r['latency_s']}s)")
            print(f"     {r['api_error'][:110]}")
        elif not r["json_ok"]:
            print(f"JSON-FAIL")
            print(f"     {r['api_error']}")
        else:
            print(f"INVALID  ({r['latency_s']}s)  [{len(r['errors'])} errors]")
            for err in r["errors"][:6]:
                loc = err["loc"] if err["loc"] else "(root)"
                print(f"     [{loc}]  {err['msg'][:90]}")

    # -- Summary table ---------------------------------------------------------
    print("\n" + "=" * W)
    print("  SUMMARY")
    print("=" * W)
    print(f"  {'Model':<33}  {'v1':^14}  {'v2':^14}")
    print("  " + "-" * (W - 2))

    for model in MODELS:
        v1r = next((r for r in results if r["model"] == model and r["pv"] == 1), None)
        v2r = next((r for r in results if r["model"] == model and r["pv"] == 2), None)

        def cell(r: dict | None) -> str:
            if r is None:
                return "   skip   "
            if r["success"]:
                return f"OK {r['latency_s']}s"
            if r["api_error"]:
                return "  API err "
            return f"{len(r['errors'])} errors"

        name = model.split("/")[-1][:32]
        print(f"  {name:<33}  {cell(v1r):^14}  {cell(v2r):^14}")

    print(f"\n  Full raw JSON + validation details -> {LOG_FILE}")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
