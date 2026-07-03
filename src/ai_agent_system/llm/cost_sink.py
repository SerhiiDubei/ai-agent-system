"""Cost sink — persists LLM call records + maintains daily rollup.

Per N10 research:
- One row per call у llm_calls (canonical)
- UPSERT daily rollup `ON CONFLICT DO UPDATE` у same transaction
- Single source of truth (NOT trust OpenRouter dashboard — UI lag)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.config import settings
from ai_agent_system.db.models.llm import LlmCall, LlmDailyRollup
from ai_agent_system.llm.exceptions import BudgetExceededException

log = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """In-memory record перед persist."""

    operation_id: str
    model_requested: str
    model_used: str
    fallback_used: bool
    provider: Optional[str]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    project_id: Optional[str] = None
    openrouter_generation_id: Optional[str] = None
    trace_id: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    extras: Optional[dict] = None


class CostSink:
    """Persists LLM call records + maintains daily rollup."""

    def __init__(self, session_factory) -> None:
        # session_factory: async callable returning AsyncSession context manager
        self._session_factory = session_factory

    async def record(self, record: CostRecord) -> int:
        """Insert call row + UPSERT daily rollup. Returns LlmCall.id.

        Single transaction so rollup і call always consistent.
        """
        async with self._session_factory() as session:
            session: AsyncSession  # type: ignore[no-redef]

            call = LlmCall(
                operation_id=record.operation_id,
                project_id=record.project_id,
                model_requested=record.model_requested,
                model_used=record.model_used,
                fallback_used=record.fallback_used,
                provider=record.provider,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                cost_usd=record.cost_usd,
                latency_ms=record.latency_ms,
                openrouter_generation_id=record.openrouter_generation_id,
                trace_id=record.trace_id,
                status=record.status,
                error_message=record.error_message,
                extras=record.extras or {},
            )
            session.add(call)
            await session.flush()  # need id

            # UPSERT daily rollup в той самий transaction
            today = date.today()
            stmt = pg_insert(LlmDailyRollup).values(
                rollup_date=today,
                operation_id=record.operation_id,
                total_calls=1,
                total_input_tokens=record.input_tokens,
                total_output_tokens=record.output_tokens,
                total_cost_usd=record.cost_usd,
                error_count=1 if record.status != "success" else 0,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["rollup_date", "operation_id"],
                set_={
                    "total_calls": LlmDailyRollup.total_calls + 1,
                    "total_input_tokens": LlmDailyRollup.total_input_tokens + record.input_tokens,
                    "total_output_tokens": LlmDailyRollup.total_output_tokens + record.output_tokens,
                    "total_cost_usd": LlmDailyRollup.total_cost_usd + record.cost_usd,
                    "error_count": LlmDailyRollup.error_count + (1 if record.status != "success" else 0),
                    "updated_at": datetime.utcnow(),
                },
            )
            await session.execute(stmt)
            await session.commit()

            log.debug(
                "recorded llm_call id=%d op=%s model=%s cost=$%.6f tokens=%d/%d",
                call.id,
                record.operation_id,
                record.model_used,
                record.cost_usd,
                record.input_tokens,
                record.output_tokens,
            )
            return call.id

    async def daily_total_usd(self, target_date: date | None = None) -> float:
        """Sum total_cost_usd across operations за дату (default today)."""
        target_date = target_date or date.today()
        async with self._session_factory() as session:
            session: AsyncSession  # type: ignore[no-redef]
            result = await session.execute(
                select(LlmDailyRollup).where(LlmDailyRollup.rollup_date == target_date)
            )
            rows = result.scalars().all()
            return sum(r.total_cost_usd for r in rows)

    async def ensure_under_daily_cap(self, attempted_usd: float | None = None) -> None:
        """Raises BudgetExceededException якщо daily cap would be exceeded."""
        cap = settings.cost_daily_cap_usd
        spent = await self.daily_total_usd()
        if attempted_usd is not None:
            if spent + attempted_usd > cap:
                raise BudgetExceededException(
                    cap_usd=cap, spent_usd=spent, attempted_usd=attempted_usd
                )
        elif spent >= cap:
            raise BudgetExceededException(cap_usd=cap, spent_usd=spent)

    async def daily_summary(self, target_date: date | None = None) -> dict:
        """Returns aggregated summary для admin endpoint."""
        target_date = target_date or date.today()
        async with self._session_factory() as session:
            session: AsyncSession  # type: ignore[no-redef]
            result = await session.execute(
                select(LlmDailyRollup).where(LlmDailyRollup.rollup_date == target_date)
            )
            rows = result.scalars().all()

        per_op = [
            {
                "operation_id": r.operation_id,
                "calls": r.total_calls,
                "input_tokens": r.total_input_tokens,
                "output_tokens": r.total_output_tokens,
                "cost_usd": round(r.total_cost_usd, 6),
                "errors": r.error_count,
            }
            for r in rows
        ]
        total_cost = sum(r.total_cost_usd for r in rows)
        total_calls = sum(r.total_calls for r in rows)
        total_errors = sum(r.error_count for r in rows)

        return {
            "date": target_date.isoformat(),
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "total_errors": total_errors,
            "daily_cap_usd": settings.cost_daily_cap_usd,
            "remaining_usd": round(settings.cost_daily_cap_usd - total_cost, 6),
            "per_operation": per_op,
        }
