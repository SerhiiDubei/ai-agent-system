"""Kill-switch для LLM gateway.

Per N10 research:
- Single Postgres bool row + 5s in-process TTL cache
- Reject NEW calls only — NEVER cancel in-flight (avoids corrupted agent state)
- Manual control via /api/v1/admin/cost/freeze + /unfreeze
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.db.models.llm import KillSwitchState
from ai_agent_system.llm.exceptions import KillSwitchActiveException

log = logging.getLogger(__name__)

# 5-second TTL per N10 — балансує DB load з reaction time
CACHE_TTL_SECONDS = 5.0


@dataclass
class _CacheEntry:
    is_active: bool
    reason: str | None
    engaged_at: datetime | None
    revision: int
    fetched_at: float  # monotonic time


class KillSwitch:
    """Process-local cache над Postgres `kill_switch_state` (single row id=1).

    Pattern: in-flight calls продовжують (no cancel — corrupted state).
    New calls check `ensure_not_engaged()` before doing work.
    """

    def __init__(self, session_factory) -> None:
        # session_factory: async callable returning AsyncSession context manager
        self._session_factory = session_factory
        self._cache: _CacheEntry | None = None

    async def _fetch(self) -> _CacheEntry:
        """Read state з DB, refresh cache."""
        async with self._session_factory() as session:
            session: AsyncSession  # type: ignore[no-redef]
            result = await session.execute(
                select(KillSwitchState).where(KillSwitchState.id == 1)
            )
            row = result.scalar_one_or_none()

        if row is None:
            # Not initialized — assume safe (not active)
            entry = _CacheEntry(
                is_active=False,
                reason=None,
                engaged_at=None,
                revision=0,
                fetched_at=time.monotonic(),
            )
        else:
            entry = _CacheEntry(
                is_active=row.is_active,
                reason=row.engaged_reason,
                engaged_at=row.engaged_at,
                revision=row.revision,
                fetched_at=time.monotonic(),
            )

        self._cache = entry
        return entry

    async def is_active(self) -> bool:
        """Returns True якщо engaged. Uses 5s cache."""
        now = time.monotonic()
        if self._cache is None or (now - self._cache.fetched_at) > CACHE_TTL_SECONDS:
            await self._fetch()
        assert self._cache is not None
        return self._cache.is_active

    async def ensure_not_engaged(self) -> None:
        """Raises KillSwitchActiveException якщо engaged. Use as guard."""
        if await self.is_active():
            assert self._cache is not None
            raise KillSwitchActiveException(
                reason=self._cache.reason,
                engaged_at=str(self._cache.engaged_at) if self._cache.engaged_at else None,
            )

    async def engage(self, reason: str | None = None) -> None:
        """Engage kill switch — reject new calls.

        Idempotent: re-engage просто bumps revision + updates reason/timestamp.
        """
        async with self._session_factory() as session:
            session: AsyncSession  # type: ignore[no-redef]
            result = await session.execute(
                select(KillSwitchState).where(KillSwitchState.id == 1).with_for_update()
            )
            row = result.scalar_one_or_none()

            now = datetime.utcnow()
            if row is None:
                row = KillSwitchState(
                    id=1,
                    is_active=True,
                    engaged_at=now,
                    engaged_reason=reason,
                    revision=1,
                )
                session.add(row)
            else:
                row.is_active = True
                row.engaged_at = now
                row.engaged_reason = reason
                row.revision += 1

            await session.commit()
            log.warning("kill switch ENGAGED reason=%r revision=%d", reason, row.revision)

        # Invalidate cache so next is_active() refetches
        self._cache = None

    async def disengage(self) -> None:
        """Disengage kill switch — allow new calls."""
        async with self._session_factory() as session:
            session: AsyncSession  # type: ignore[no-redef]
            result = await session.execute(
                select(KillSwitchState).where(KillSwitchState.id == 1).with_for_update()
            )
            row = result.scalar_one_or_none()

            if row is None or not row.is_active:
                log.info("disengage called but already inactive")
                return

            row.is_active = False
            row.revision += 1
            await session.commit()
            log.warning("kill switch DISENGAGED revision=%d", row.revision)

        self._cache = None

    async def status(self) -> dict[str, object]:
        """Returns current state dict — for /api/v1/admin/cost/status endpoint."""
        # Force refetch для accurate status
        entry = await self._fetch()
        return {
            "is_active": entry.is_active,
            "reason": entry.reason,
            "engaged_at": entry.engaged_at.isoformat() if entry.engaged_at else None,
            "revision": entry.revision,
        }
