"""Integration tests для CostSink — Postgres з UPSERT."""

from datetime import date

import pytest
from sqlalchemy import select

from ai_agent_system.db.models.llm import LlmCall, LlmDailyRollup
from ai_agent_system.llm.cost_sink import CostRecord, CostSink
from ai_agent_system.llm.exceptions import BudgetExceededException


pytestmark = pytest.mark.integration


@pytest.fixture
def session_factory(db_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
def sink(session_factory) -> CostSink:
    return CostSink(session_factory)


def make_record(
    operation_id: str = "agent.copy_expert",
    cost_usd: float = 0.05,
    project_id: str | None = "proj_test",
    status: str = "success",
) -> CostRecord:
    return CostRecord(
        operation_id=operation_id,
        project_id=project_id,
        model_requested="anthropic/claude-3.5-sonnet",
        model_used="anthropic/claude-3.5-sonnet",
        fallback_used=False,
        provider="Anthropic",
        input_tokens=120,
        output_tokens=300,
        cost_usd=cost_usd,
        latency_ms=2400,
        status=status,
    )


async def test_records_call_and_creates_rollup(sink: CostSink, session_factory) -> None:
    rec = make_record(cost_usd=0.05)
    call_id = await sink.record(rec)
    assert call_id > 0

    async with session_factory() as session:
        # Call row exists
        result = await session.execute(select(LlmCall).where(LlmCall.id == call_id))
        row = result.scalar_one()
        assert row.operation_id == "agent.copy_expert"
        assert row.cost_usd == pytest.approx(0.05)
        assert row.status == "success"

        # Rollup created для today
        result = await session.execute(
            select(LlmDailyRollup).where(
                LlmDailyRollup.rollup_date == date.today(),
                LlmDailyRollup.operation_id == "agent.copy_expert",
            )
        )
        rollup = result.scalar_one()
        assert rollup.total_calls == 1
        assert rollup.total_cost_usd == pytest.approx(0.05)
        assert rollup.error_count == 0


async def test_records_aggregate_in_rollup(sink: CostSink, session_factory) -> None:
    await sink.record(make_record(cost_usd=0.05))
    await sink.record(make_record(cost_usd=0.07))
    await sink.record(make_record(cost_usd=0.03))

    async with session_factory() as session:
        result = await session.execute(
            select(LlmDailyRollup).where(
                LlmDailyRollup.operation_id == "agent.copy_expert"
            )
        )
        rollup = result.scalar_one()
        assert rollup.total_calls == 3
        assert rollup.total_cost_usd == pytest.approx(0.15)


async def test_records_per_operation_separately(
    sink: CostSink, session_factory
) -> None:
    await sink.record(make_record("agent.copy_expert", 0.05))
    await sink.record(make_record("agent.uxui_expert", 0.04))

    async with session_factory() as session:
        result = await session.execute(select(LlmDailyRollup))
        rollups = result.scalars().all()
        ops = {r.operation_id: r for r in rollups}
        assert "agent.copy_expert" in ops
        assert "agent.uxui_expert" in ops
        assert ops["agent.copy_expert"].total_cost_usd == pytest.approx(0.05)


async def test_error_increments_error_count(sink: CostSink, session_factory) -> None:
    await sink.record(make_record(status="success", cost_usd=0.0))
    await sink.record(make_record(status="error", cost_usd=0.0))

    async with session_factory() as session:
        result = await session.execute(select(LlmDailyRollup))
        rollup = result.scalar_one()
        assert rollup.total_calls == 2
        assert rollup.error_count == 1


async def test_daily_total_usd(sink: CostSink) -> None:
    await sink.record(make_record("agent.copy_expert", 0.10))
    await sink.record(make_record("agent.uxui_expert", 0.04))
    total = await sink.daily_total_usd()
    assert total == pytest.approx(0.14)


async def test_ensure_under_daily_cap_passes_when_under(
    sink: CostSink, monkeypatch
) -> None:
    from ai_agent_system.config import settings

    monkeypatch.setattr(settings, "cost_daily_cap_usd", 5.0)
    await sink.record(make_record(cost_usd=1.0))
    # Should not raise: spent 1.0, attempting 0.5, cap 5.0
    await sink.ensure_under_daily_cap(attempted_usd=0.5)


async def test_ensure_under_daily_cap_raises_when_would_exceed(
    sink: CostSink, monkeypatch
) -> None:
    from ai_agent_system.config import settings

    monkeypatch.setattr(settings, "cost_daily_cap_usd", 1.0)
    await sink.record(make_record(cost_usd=0.8))
    with pytest.raises(BudgetExceededException) as exc:
        await sink.ensure_under_daily_cap(attempted_usd=0.5)
    assert exc.value.cap_usd == 1.0
    assert exc.value.spent_usd == pytest.approx(0.8)


async def test_daily_summary_shape(sink: CostSink) -> None:
    await sink.record(make_record("agent.copy_expert", 0.05))
    await sink.record(make_record("agent.uxui_expert", 0.03))

    summary = await sink.daily_summary()
    assert summary["total_calls"] == 2
    assert summary["total_cost_usd"] == pytest.approx(0.08)
    assert "remaining_usd" in summary
    assert "per_operation" in summary
    assert len(summary["per_operation"]) == 2
