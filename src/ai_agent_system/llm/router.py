"""LlmRouter — main entrypoint для всіх LLM calls.

Per N10 research:
- bare openai.AsyncOpenAI з base_url override → OpenRouter (NO LiteLLM)
- Per-operation routing via YAML
- Native OpenRouter fallbacks via extra_body.models
- Provider pinning via extra_body.provider.order
- usage.cost ALWAYS returned (last SSE chunk у streams) — captured directly
- Tenacity ONLY for connection/timeout errors (NOT 429s — OpenRouter handles)
- Kill switch + daily budget enforcement on every call
- Cost sink writes after EVERY call (success or failure)
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_agent_system.config import settings
from ai_agent_system.llm.cost_sink import CostRecord, CostSink
from ai_agent_system.llm.kill_switch import KillSwitch
from ai_agent_system.llm.routing_config import RoutingConfig
from ai_agent_system.llm.tracing import get_current_trace_id, wrap_with_langsmith

log = logging.getLogger(__name__)


def _build_openai_client() -> AsyncOpenAI:
    """Build raw AsyncOpenAI з OpenRouter base_url + LangSmith wrap."""
    raw_client = AsyncOpenAI(
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url=settings.openrouter_base_url,
        timeout=90.0,
        # NOTE: do NOT set max_retries here — we control retries via tenacity
        max_retries=0,
    )
    return wrap_with_langsmith(raw_client)


class LlmRouter:
    """Entrypoint для всіх LLM calls. Operation-keyed routing.

    Usage:
        router = LlmRouter(routing_config, cost_sink, kill_switch)
        response = await router.chat(
            operation="agent.copy_expert",
            messages=[{"role": "user", "content": "..."}],
            project_id="proj_123",
        )
    """

    def __init__(
        self,
        routing_config: RoutingConfig,
        cost_sink: CostSink,
        kill_switch: KillSwitch,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._config = routing_config
        self._cost_sink = cost_sink
        self._kill_switch = kill_switch
        self.client = client if client is not None else _build_openai_client()

    @property
    def openai_client(self) -> AsyncOpenAI:
        """Expose underlying client for Pydantic AI integration:

        from pydantic_ai.providers.openrouter import OpenRouterProvider
        provider = OpenRouterProvider(openai_client=router.openai_client)
        """
        return self.client

    async def chat(
        self,
        operation: str,
        messages: list[dict[str, Any]],
        *,
        project_id: Optional[str] = None,
        **extra_kwargs: Any,
    ) -> ChatCompletion:
        """Non-streaming chat completion.

        Args:
            operation: routing key (e.g. "agent.copy_expert"). Must exist in YAML.
            messages: OpenAI-compatible messages list.
            project_id: optional tag для cost attribution.
            extra_kwargs: passed through to client.chat.completions.create.

        Returns:
            ChatCompletion з usage populated. Cost recorded automatically.

        Raises:
            KillSwitchActiveException, BudgetExceededException,
            OperationNotConfiguredException.
        """
        # 1. Pre-flight checks
        await self._kill_switch.ensure_not_engaged()
        await self._cost_sink.ensure_under_daily_cap()

        # 2. Resolve routing
        op_cfg = self._config.get_operation(operation)
        defaults = self._config.defaults

        request_kwargs = {
            "model": op_cfg.model,
            "messages": messages,
            "temperature": extra_kwargs.pop("temperature", defaults.temperature),
            "timeout": extra_kwargs.pop("timeout", defaults.timeout_seconds),
        }

        # OpenRouter native fallbacks via extra_body
        extra_body: dict[str, Any] = extra_kwargs.pop("extra_body", {}) or {}
        if op_cfg.fallback_models:
            extra_body.setdefault(
                "models",
                [op_cfg.model, *op_cfg.fallback_models],
            )
        if op_cfg.provider_pin:
            extra_body.setdefault(
                "provider",
                {"order": op_cfg.provider_pin, "allow_fallbacks": False},
            )
        if extra_body:
            request_kwargs["extra_body"] = extra_body

        extra_headers: dict[str, str] = extra_kwargs.pop("extra_headers", {}) or {}
        extra_headers.setdefault("HTTP-Referer", settings.openrouter_http_referer)
        extra_headers.setdefault("X-Title", settings.openrouter_app_title)
        request_kwargs["extra_headers"] = extra_headers

        # Pass through anything else (max_tokens, response_format, tools etc.)
        request_kwargs.update(extra_kwargs)

        # 3. Call з tenacity retry (connection/timeout only — NOT 429)
        from openai import APIConnectionError, APITimeoutError

        retry_policy = AsyncRetrying(
            stop=stop_after_attempt(defaults.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((APIConnectionError, APITimeoutError)),
            reraise=True,
        )

        started = time.monotonic()
        response: ChatCompletion | None = None
        error_msg: Optional[str] = None
        try:
            async for attempt in retry_policy:
                with attempt:
                    response = await self.client.chat.completions.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001 — record error then re-raise
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            await self._record_cost(
                operation_id=operation,
                project_id=project_id,
                model_requested=op_cfg.model,
                response=response,
                latency_ms=latency_ms,
                error_msg=error_msg,
            )

        assert response is not None
        return response

    async def chat_stream(
        self,
        operation: str,
        messages: list[dict[str, Any]],
        *,
        project_id: Optional[str] = None,
        **extra_kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Streaming variant. Cost captured з last SSE chunk.

        Per N10: usage.cost ALWAYS returned in last chunk (2026 OpenRouter behavior).
        """
        await self._kill_switch.ensure_not_engaged()
        await self._cost_sink.ensure_under_daily_cap()

        op_cfg = self._config.get_operation(operation)
        defaults = self._config.defaults

        extra_body: dict[str, Any] = extra_kwargs.pop("extra_body", {}) or {}
        if op_cfg.fallback_models:
            extra_body.setdefault("models", [op_cfg.model, *op_cfg.fallback_models])
        if op_cfg.provider_pin:
            extra_body.setdefault(
                "provider", {"order": op_cfg.provider_pin, "allow_fallbacks": False}
            )

        extra_headers: dict[str, str] = extra_kwargs.pop("extra_headers", {}) or {}
        extra_headers.setdefault("HTTP-Referer", settings.openrouter_http_referer)
        extra_headers.setdefault("X-Title", settings.openrouter_app_title)

        request_kwargs = {
            "model": op_cfg.model,
            "messages": messages,
            "temperature": extra_kwargs.pop("temperature", defaults.temperature),
            "stream": True,
            "extra_body": extra_body if extra_body else None,
            "extra_headers": extra_headers,
            **extra_kwargs,
        }
        # Drop None
        request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}

        started = time.monotonic()
        last_chunk_with_usage: Any = None
        error_msg: Optional[str] = None
        try:
            stream = await self.client.chat.completions.create(**request_kwargs)
            async for chunk in stream:
                if getattr(chunk, "usage", None) is not None:
                    last_chunk_with_usage = chunk
                yield chunk
        except Exception as exc:  # noqa: BLE001
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            await self._record_cost(
                operation_id=operation,
                project_id=project_id,
                model_requested=op_cfg.model,
                response=last_chunk_with_usage,
                latency_ms=latency_ms,
                error_msg=error_msg,
            )

    async def _record_cost(
        self,
        *,
        operation_id: str,
        project_id: Optional[str],
        model_requested: str,
        response: Any,
        latency_ms: int,
        error_msg: Optional[str],
    ) -> None:
        """Extract usage з response → CostRecord → persist via CostSink."""
        # Defaults — на випадок коли response None (full failure)
        model_used = model_requested
        fallback_used = False
        provider: Optional[str] = None
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
        gen_id: Optional[str] = None

        if response is not None:
            try:
                model_used = getattr(response, "model", model_requested) or model_requested
                fallback_used = model_used != model_requested

                usage = getattr(response, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(usage, "completion_tokens", 0) or 0
                    # OpenRouter-specific fields:
                    cost_usd = float(getattr(usage, "cost", 0.0) or 0.0)

                # OpenRouter generation id для re-query reconciliation
                gen_id = getattr(response, "id", None)
                provider = getattr(response, "provider", None) or None
            except Exception as exc:  # noqa: BLE001
                log.warning("failed to extract usage з response: %s", exc)

        record = CostRecord(
            operation_id=operation_id,
            project_id=project_id,
            model_requested=model_requested,
            model_used=model_used,
            fallback_used=fallback_used,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            openrouter_generation_id=gen_id,
            trace_id=get_current_trace_id(),
            status="success" if error_msg is None else "error",
            error_message=error_msg,
        )

        try:
            await self._cost_sink.record(record)
        except Exception as exc:  # noqa: BLE001 — never let cost recording break a real call
            log.error("failed to record cost: %s (record=%r)", exc, record)
