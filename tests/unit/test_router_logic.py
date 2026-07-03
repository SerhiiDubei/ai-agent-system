"""Unit tests для LlmRouter — мокаємо OpenAI client + DB через protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_agent_system.llm.cost_sink import CostRecord
from ai_agent_system.llm.exceptions import (
    BudgetExceededException,
    KillSwitchActiveException,
    OperationNotConfiguredException,
)
from ai_agent_system.llm.router import LlmRouter
from ai_agent_system.llm.routing_config import OperationRouting, RoutingConfig


@dataclass
class _StubResponse:
    """Mimic openai.types.chat.ChatCompletion enough для cost extraction."""

    id: str
    model: str
    usage: Any
    provider: str | None = None


@dataclass
class _StubUsage:
    prompt_tokens: int
    completion_tokens: int
    cost: float


class _StubChatCompletions:
    def __init__(self, response: _StubResponse) -> None:
        self._response = response
        self.last_call_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _StubResponse:
        self.last_call_kwargs = kwargs
        return self._response


class _StubOpenAI:
    def __init__(self, response: _StubResponse) -> None:
        completions = _StubChatCompletions(response)
        self.chat = MagicMock()
        self.chat.completions = completions


@pytest.fixture
def routing_config(tmp_path) -> RoutingConfig:
    import yaml

    cfg = {
        "defaults": {"temperature": 0.0, "max_retries": 1, "timeout_seconds": 30},
        "operations": {
            "agent.copy_expert": {
                "model": "anthropic/claude-3.5-sonnet",
                "fallback_models": ["openai/gpt-4o"],
            },
        },
    }
    p = tmp_path / "llm_routing.yml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return RoutingConfig(config_path=p)


@pytest.fixture
def stub_response() -> _StubResponse:
    return _StubResponse(
        id="gen-test-001",
        model="anthropic/claude-3.5-sonnet",
        usage=_StubUsage(prompt_tokens=100, completion_tokens=200, cost=0.0042),
        provider="Anthropic",
    )


@pytest.fixture
def stub_client(stub_response: _StubResponse) -> _StubOpenAI:
    return _StubOpenAI(stub_response)


@pytest.fixture
def cost_sink_mock() -> AsyncMock:
    sink = AsyncMock()
    sink.ensure_under_daily_cap = AsyncMock(return_value=None)
    sink.record = AsyncMock(return_value=42)
    return sink


@pytest.fixture
def kill_switch_mock() -> AsyncMock:
    ks = AsyncMock()
    ks.ensure_not_engaged = AsyncMock(return_value=None)
    return ks


@pytest.fixture
def router(
    routing_config: RoutingConfig,
    cost_sink_mock: AsyncMock,
    kill_switch_mock: AsyncMock,
    stub_client: _StubOpenAI,
) -> LlmRouter:
    return LlmRouter(
        routing_config=routing_config,
        cost_sink=cost_sink_mock,
        kill_switch=kill_switch_mock,
        client=stub_client,  # type: ignore[arg-type]
    )


async def test_chat_returns_response(router: LlmRouter) -> None:
    response = await router.chat(
        operation="agent.copy_expert",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert response.id == "gen-test-001"


async def test_chat_records_cost(
    router: LlmRouter, cost_sink_mock: AsyncMock
) -> None:
    await router.chat(
        operation="agent.copy_expert",
        messages=[{"role": "user", "content": "hi"}],
        project_id="proj_123",
    )
    cost_sink_mock.record.assert_called_once()
    record: CostRecord = cost_sink_mock.record.call_args.args[0]
    assert record.operation_id == "agent.copy_expert"
    assert record.project_id == "proj_123"
    assert record.input_tokens == 100
    assert record.output_tokens == 200
    assert record.cost_usd == pytest.approx(0.0042)
    assert record.openrouter_generation_id == "gen-test-001"
    assert record.status == "success"


async def test_chat_passes_fallback_models_via_extra_body(
    router: LlmRouter, stub_client: _StubOpenAI
) -> None:
    await router.chat(
        operation="agent.copy_expert",
        messages=[{"role": "user", "content": "hi"}],
    )
    kwargs = stub_client.chat.completions.last_call_kwargs
    assert "extra_body" in kwargs
    assert kwargs["extra_body"]["models"] == [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
    ]


async def test_chat_sets_openrouter_headers(
    router: LlmRouter, stub_client: _StubOpenAI
) -> None:
    await router.chat(
        operation="agent.copy_expert",
        messages=[{"role": "user", "content": "hi"}],
    )
    kwargs = stub_client.chat.completions.last_call_kwargs
    assert "extra_headers" in kwargs
    assert "HTTP-Referer" in kwargs["extra_headers"]
    assert "X-Title" in kwargs["extra_headers"]


async def test_chat_unknown_operation_raises(router: LlmRouter) -> None:
    with pytest.raises(OperationNotConfiguredException):
        await router.chat(
            operation="not.configured", messages=[{"role": "user", "content": "x"}]
        )


async def test_chat_kill_switch_active_raises(
    router: LlmRouter, kill_switch_mock: AsyncMock
) -> None:
    kill_switch_mock.ensure_not_engaged.side_effect = KillSwitchActiveException(
        reason="test"
    )
    with pytest.raises(KillSwitchActiveException):
        await router.chat(
            operation="agent.copy_expert",
            messages=[{"role": "user", "content": "x"}],
        )


async def test_chat_budget_exceeded_raises(
    router: LlmRouter, cost_sink_mock: AsyncMock
) -> None:
    cost_sink_mock.ensure_under_daily_cap.side_effect = BudgetExceededException(
        cap_usd=5.0, spent_usd=5.0
    )
    with pytest.raises(BudgetExceededException):
        await router.chat(
            operation="agent.copy_expert",
            messages=[{"role": "user", "content": "x"}],
        )
