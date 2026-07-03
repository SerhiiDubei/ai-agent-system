"""Integration tests для KillSwitch — Postgres state з Testcontainers."""

import pytest

from ai_agent_system.db.models.llm import KillSwitchState
from ai_agent_system.llm.exceptions import KillSwitchActiveException
from ai_agent_system.llm.kill_switch import KillSwitch


pytestmark = pytest.mark.integration


@pytest.fixture
async def session_factory(db_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def kill_switch_with_seed(session_factory):
    """Seed singleton kill_switch_state row (matches V0001 migration behavior)."""
    async with session_factory() as session:
        session.add(KillSwitchState(id=1, is_active=False, revision=0))
        await session.commit()
    return KillSwitch(session_factory)


async def test_initially_inactive(kill_switch_with_seed: KillSwitch) -> None:
    assert await kill_switch_with_seed.is_active() is False
    # ensure_not_engaged should not raise
    await kill_switch_with_seed.ensure_not_engaged()


async def test_engage_then_active(kill_switch_with_seed: KillSwitch) -> None:
    await kill_switch_with_seed.engage(reason="cost spike detected")
    assert await kill_switch_with_seed.is_active() is True

    with pytest.raises(KillSwitchActiveException) as exc:
        await kill_switch_with_seed.ensure_not_engaged()
    assert "cost spike detected" in str(exc.value)


async def test_disengage(kill_switch_with_seed: KillSwitch) -> None:
    await kill_switch_with_seed.engage(reason="test")
    await kill_switch_with_seed.disengage()
    assert await kill_switch_with_seed.is_active() is False


async def test_engage_idempotent_bumps_revision(
    kill_switch_with_seed: KillSwitch,
) -> None:
    await kill_switch_with_seed.engage(reason="first")
    status1 = await kill_switch_with_seed.status()
    rev1 = status1["revision"]

    await kill_switch_with_seed.engage(reason="second")
    status2 = await kill_switch_with_seed.status()

    assert status2["revision"] == rev1 + 1
    assert status2["reason"] == "second"


async def test_disengage_when_already_inactive_is_noop(
    kill_switch_with_seed: KillSwitch,
) -> None:
    # Should not raise, should not bump revision
    status_before = await kill_switch_with_seed.status()
    await kill_switch_with_seed.disengage()
    status_after = await kill_switch_with_seed.status()
    assert status_before["revision"] == status_after["revision"]


async def test_status_returns_full_state(kill_switch_with_seed: KillSwitch) -> None:
    await kill_switch_with_seed.engage(reason="full test")
    status = await kill_switch_with_seed.status()
    assert status["is_active"] is True
    assert status["reason"] == "full test"
    assert status["engaged_at"] is not None
    assert status["revision"] >= 1
