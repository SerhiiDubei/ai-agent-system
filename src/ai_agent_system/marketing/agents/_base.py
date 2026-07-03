"""Shared utilities for the 5 character-driven agents.

Three responsibilities:
  1. Load character-card prompts from prompts/<agent>/v<N>.md
  2. Build Pydantic AI agents from agent config + character card + output schema
  3. Run agents with auto-fallback chain (primary model → fallback_models[0] → ...)
     and full observability logging

Why we own the fallback loop instead of using pydantic-ai's `retries`:
  pydantic-ai retries on the SAME model. Our fallback model rotates through
  configured chain, which is a smarter strategy when a model is "confidently
  wrong" about the schema (no amount of self-correction will fix it).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, TypeVar

from openai import AsyncOpenAI
from openai import APIError as OpenAIAPIError
from openai import BadRequestError as OpenAIBadRequestError
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_agent_system.benchmark.types import estimate_cost
from ai_agent_system.config import settings
from ai_agent_system.observability.agent_logger import AgentInvocationLogger
from ai_agent_system.observability.config_loader import AgentConfig
from ai_agent_system.observability.models import LLMCallRecord

log = logging.getLogger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)

PROMPTS_ROOT = Path(__file__).resolve().parents[4] / "prompts"


# ── Prompt loader ────────────────────────────────────────────────────────────

def load_character_card(agent_name: str, version: str) -> str:
    """Load prompts/<agent>/<version>.md as a string."""
    path = PROMPTS_ROOT / agent_name / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Character card not found: {path}. "
            f"Create the file or check prompt_versions in agents.yml."
        )
    return path.read_text(encoding="utf-8")


# ── Pydantic AI agent factory ────────────────────────────────────────────────

def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
    )


def build_pydantic_agent(
    *,
    model_id: str,
    system_prompt: str,
    output_type: type[OutputT],
    temperature: float,
    max_tokens: int,
) -> Agent[None, OutputT]:
    """Build a fresh Pydantic AI Agent with one specific model.

    NOTE: We intentionally pass retries=0 — fallback chain is handled by
    run_with_fallback() at a higher level.
    """
    return Agent(
        model=OpenAIModel(model_name=model_id, provider=_provider()),
        deps_type=type(None),
        output_type=output_type,
        system_prompt=system_prompt,
        model_settings={
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        retries=0,
    )


# ── Run with fallback chain + observability ──────────────────────────────────

class FallbackChainExhausted(Exception):
    """Every model in the fallback chain failed."""


async def run_with_fallback(
    *,
    agent_name: str,
    config: AgentConfig,
    system_prompt: str,
    user_prompt: str,
    output_type: type[OutputT],
    invocation_logger: AgentInvocationLogger,
) -> OutputT:
    """Run agent through primary + fallback models until one succeeds.

    For each attempt:
      - Builds fresh Pydantic AI Agent with that model
      - Logs LLM call (system_prompt, user_prompt, raw_response or error)
      - On ValidationError or UnexpectedModelBehavior → tries next model
      - On success → logs validation passed, returns the typed output

    Raises FallbackChainExhausted if all models fail.
    """
    chain = [config.model] + list(config.fallback_models)

    last_error: Exception | None = None

    for attempt_num, model_id in enumerate(chain, start=1):
        log.info(
            "agent=%s attempt=%d/%d model=%s",
            agent_name, attempt_num, len(chain), model_id,
        )
        agent = build_pydantic_agent(
            model_id=model_id,
            system_prompt=system_prompt,
            output_type=output_type,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        t0 = time.monotonic()
        try:
            result = await agent.run(user_prompt)
            latency_ms = int((time.monotonic() - t0) * 1000)

            # Capture usage + cost
            usage = result.usage()
            in_tok = getattr(usage, "input_tokens", 0) or 0
            out_tok = getattr(usage, "output_tokens", 0) or 0
            cost = estimate_cost(model_id, in_tok, out_tok)

            # Capture raw output (the structured object the model produced)
            raw_response = result.output.model_dump_json(indent=2)

            invocation_logger.log_llm_call(LLMCallRecord(
                model=model_id,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=raw_response,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                latency_ms=latency_ms,
                attempt_number=attempt_num,
            ))
            invocation_logger.log_validation(passed=True)
            return result.output

        except (ValidationError, UnexpectedModelBehavior) as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            err_type = type(e).__name__
            err_str = str(e)[:2000]  # cap to avoid massive log entries

            invocation_logger.log_llm_call(LLMCallRecord(
                model=model_id,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=None,
                error=err_str,
                error_type=err_type,
                latency_ms=latency_ms,
                attempt_number=attempt_num,
            ))

            # Extract validation error details if available
            errors_list: list[dict] = []
            if isinstance(e, ValidationError):
                errors_list = [
                    {
                        "loc": " -> ".join(str(x) for x in err["loc"]),
                        "msg": err["msg"],
                        "type": err["type"],
                    }
                    for err in e.errors(include_url=False)[:10]
                ]
            invocation_logger.log_validation(
                passed=False,
                errors=errors_list,
                message=f"{err_type} from {model_id} (attempt {attempt_num})",
            )

            last_error = e
            log.warning(
                "agent=%s model=%s attempt=%d failed (%s) — trying next in chain",
                agent_name, model_id, attempt_num, err_type,
            )
            continue

        except Exception as e:  # network, timeout, API error
            latency_ms = int((time.monotonic() - t0) * 1000)
            err_type = type(e).__name__
            err_str = str(e)[:2000]

            invocation_logger.log_llm_call(LLMCallRecord(
                model=model_id,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=None,
                error=err_str,
                error_type=err_type,
                latency_ms=latency_ms,
                attempt_number=attempt_num,
            ))

            last_error = e
            log.warning(
                "agent=%s model=%s attempt=%d API error %s — trying next",
                agent_name, model_id, attempt_num, err_type,
            )
            continue

    # All models exhausted
    raise FallbackChainExhausted(
        f"All {len(chain)} models failed for agent '{agent_name}'. "
        f"Last error: {type(last_error).__name__}: {last_error}"
    ) from last_error


# ── Direct OpenAI API mode (for deeply-nested schemas pydantic-ai can't tool-call) ──
# When a schema has 50+ fields with nested lists of objects + enums, pydantic-ai's
# tool calling wrapper produces a tool definition models can't fill. Direct API
# with json_object mode is more permissive: model writes plain JSON, we validate
# manually. We always capture raw_response for debugging.

def _extract_json(raw: str) -> str:
    """Extract first JSON object from a response that may have prose preamble."""
    raw = raw.strip()
    if raw.startswith("```"):
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
    first = raw.find("{")
    if first >= 0:
        return raw[first:]
    return raw


async def run_with_fallback_direct(
    *,
    agent_name: str,
    config: AgentConfig,
    system_prompt: str,
    user_prompt: str,
    output_type: type[OutputT],
    invocation_logger: AgentInvocationLogger,
) -> OutputT:
    """Run agent through fallback chain using direct OpenAI API + json_object mode.

    Use this when pydantic-ai tool-calling fails on complex schemas.
    Always logs raw_response (success or fail) for debugging.
    """
    client = AsyncOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
        default_headers={
            "HTTP-Referer": "https://github.com/ai-agent-system",
            "X-Title": f"AI Agent System / {agent_name}",
        },
    )

    chain = [config.model] + list(config.fallback_models)
    last_error: Exception | None = None

    # Inject the JSON schema right into the system prompt so the model knows the contract
    schema_block = (
        "\n\n=== EXPECTED JSON OUTPUT SCHEMA ===\n"
        + json.dumps(output_type.model_json_schema(), indent=2)
        + "\n=== END SCHEMA ===\n\n"
        "Output ONLY a single JSON object matching the schema above. "
        "No markdown, no preamble, no explanation. Start with '{'."
    )
    full_system = system_prompt + schema_block

    for attempt_num, model_id in enumerate(chain, start=1):
        log.info(
            "agent=%s [direct] attempt=%d/%d model=%s",
            agent_name, attempt_num, len(chain), model_id,
        )

        t0 = time.monotonic()
        raw_text: str = ""
        try:
            kwargs: dict[str, Any] = dict(
                model=model_id,
                messages=[
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout_s,
            )
            try:
                resp = await client.chat.completions.create(
                    **kwargs,
                    response_format={"type": "json_object"},
                )
            except OpenAIBadRequestError as e:
                # json_object mode rejected (some Anthropic models via OR) — retry plain
                log.warning("json_object mode rejected (%s) — retrying plain", e.code)
                resp = await client.chat.completions.create(**kwargs)

            latency_ms = int((time.monotonic() - t0) * 1000)
            raw_text = (resp.choices[0].message.content or "").strip()

            # Extract usage if present (some providers don't return it)
            in_tok = getattr(resp.usage, "prompt_tokens", 0) or 0
            out_tok = getattr(resp.usage, "completion_tokens", 0) or 0
            cost = estimate_cost(model_id, in_tok, out_tok)

            extracted = _extract_json(raw_text)

            # Try parse + validate
            try:
                data = json.loads(extracted)
            except json.JSONDecodeError as e:
                invocation_logger.log_llm_call(LLMCallRecord(
                    model=model_id,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    system_prompt=full_system,
                    user_prompt=user_prompt,
                    raw_response=raw_text,    # always capture
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    error=f"JSON parse: {e}",
                    error_type="JSONDecodeError",
                    attempt_number=attempt_num,
                ))
                invocation_logger.log_validation(
                    passed=False, errors=[],
                    message=f"JSONDecodeError on {model_id}: {e}",
                )
                last_error = e
                continue

            try:
                validated = output_type.model_validate(data)
            except ValidationError as e:
                errors_list = [
                    {
                        "loc": " -> ".join(str(x) for x in err["loc"]),
                        "msg": err["msg"],
                        "type": err["type"],
                    }
                    for err in e.errors(include_url=False)[:15]
                ]
                invocation_logger.log_llm_call(LLMCallRecord(
                    model=model_id,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    system_prompt=full_system,
                    user_prompt=user_prompt,
                    raw_response=raw_text,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    error=f"Validation: {len(errors_list)} errors",
                    error_type="ValidationError",
                    attempt_number=attempt_num,
                ))
                invocation_logger.log_validation(
                    passed=False, errors=errors_list,
                    message=f"ValidationError ({len(errors_list)}) on {model_id}",
                )
                last_error = e
                continue

            # Success
            invocation_logger.log_llm_call(LLMCallRecord(
                model=model_id,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                system_prompt=full_system,
                user_prompt=user_prompt,
                raw_response=raw_text,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                latency_ms=latency_ms,
                attempt_number=attempt_num,
            ))
            invocation_logger.log_validation(passed=True)
            return validated

        except OpenAIAPIError as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            invocation_logger.log_llm_call(LLMCallRecord(
                model=model_id,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                system_prompt=full_system,
                user_prompt=user_prompt,
                raw_response=raw_text or None,
                latency_ms=latency_ms,
                error=str(e)[:1500],
                error_type=type(e).__name__,
                attempt_number=attempt_num,
            ))
            last_error = e
            log.warning(
                "agent=%s [direct] model=%s attempt=%d API error %s",
                agent_name, model_id, attempt_num, type(e).__name__,
            )
            continue

    raise FallbackChainExhausted(
        f"[direct] All {len(chain)} models failed for agent '{agent_name}'. "
        f"Last error: {type(last_error).__name__}: {last_error}"
    ) from last_error
