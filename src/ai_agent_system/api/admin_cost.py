"""Admin cost endpoints — /api/v1/admin/cost/*.

- GET /summary?date=YYYY-MM-DD → daily rollup
- GET /status → kill switch state + today summary
- POST /freeze → engage kill switch
- POST /unfreeze → disengage kill switch
- GET /operations → list configured operation_ids
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_agent_system.api.dependencies import (
    get_cost_sink,
    get_kill_switch,
)
from ai_agent_system.auth import require_internal_auth
from ai_agent_system.llm.cost_sink import CostSink
from ai_agent_system.llm.kill_switch import KillSwitch
from ai_agent_system.llm.routing_config import get_routing_config

router = APIRouter(dependencies=[Depends(require_internal_auth)])


class FreezeRequest(BaseModel):
    reason: str | None = None


@router.get("/summary")
async def cost_summary(
    target_date: date_type | None = Query(None, alias="date"),
    sink: CostSink = Depends(get_cost_sink),
) -> dict:
    """Daily summary aggregated by operation_id."""
    return await sink.daily_summary(target_date)


@router.get("/status")
async def cost_status(
    sink: CostSink = Depends(get_cost_sink),
    kill_switch: KillSwitch = Depends(get_kill_switch),
) -> dict:
    """Combined view: kill switch + today's spend."""
    summary = await sink.daily_summary()
    ks = await kill_switch.status()
    return {
        "kill_switch": ks,
        "today": summary,
    }


@router.post("/freeze")
async def cost_freeze(
    body: FreezeRequest,
    kill_switch: KillSwitch = Depends(get_kill_switch),
) -> dict:
    """Engage kill switch — reject ALL new LLM calls (in-flight продовжать)."""
    await kill_switch.engage(reason=body.reason)
    return await kill_switch.status()


@router.post("/unfreeze")
async def cost_unfreeze(
    kill_switch: KillSwitch = Depends(get_kill_switch),
) -> dict:
    """Disengage kill switch — allow new calls."""
    await kill_switch.disengage()
    return await kill_switch.status()


@router.get("/operations")
async def list_operations() -> dict:
    """List all routed operation_ids — для debug + UI."""
    cfg = get_routing_config()
    return {
        "operations": [
            {
                "operation_id": op_id,
                "model": cfg.get_operation(op_id).model,
                "fallback_models": cfg.get_operation(op_id).fallback_models,
                "provider_pin": cfg.get_operation(op_id).provider_pin,
                "notes": cfg.get_operation(op_id).notes,
            }
            for op_id in cfg.operation_ids
        ],
        "defaults": {
            "temperature": cfg.defaults.temperature,
            "max_retries": cfg.defaults.max_retries,
            "timeout_seconds": cfg.defaults.timeout_seconds,
        },
    }
