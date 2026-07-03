"""REST API for Marketing Context — N4.

POST /api/v1/marketing/contexts        → draft new context
GET  /api/v1/marketing/contexts/{id}  → get context by ID
POST /api/v1/marketing/contexts/{id}/approve → approve (gates downstream agents)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ai_agent_system.api.dependencies import get_db, require_internal_key
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.marketing.service import (
    approve_context,
    generate_marketing_context,
    get_context,
)

router = APIRouter()


class CreateContextRequest(BaseModel):
    brief: str = Field(..., min_length=20, description="1-paragraph description of the project")
    niche: str = Field(..., description="e.g. 'walk-in-tub', 'dating', 'solar'")
    parent_category: str = Field(..., description="e.g. 'home-improvement', 'lead-gen'")
    market: str = Field(default="US", description="ISO country/region, e.g. 'US-FL'")
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    traffic_source_primary: str = Field(
        ...,
        description="meta | google_search | google_display | tiktok | snapchat | youtube | email | organic",
    )
    page_goal: str = Field(
        ...,
        description="zip_submit | phone_call | lead_form | quiz_complete | book_demo | signup",
    )
    primary_metric: str = Field(default="cost_per_lead", description="KPI to optimize")
    business_constraints: str | None = Field(None, description="Optional constraints")


class CreateContextResponse(BaseModel):
    context_id: int
    status: str
    judge_passed: bool
    judge_issues: list[str]
    attempts: int
    latency_ms: int


class ApproveResponse(BaseModel):
    context_id: int
    status: str


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateContextResponse,
    dependencies=[Depends(require_internal_key)],
)
async def create_context(
    req: CreateContextRequest,
    session: AsyncSession = Depends(get_db),
) -> CreateContextResponse:
    result = await generate_marketing_context(
        session=session,
        brief=req.brief,
        niche=req.niche,
        parent_category=req.parent_category,
        market=req.market,
        language=req.language,
        traffic_source_primary=req.traffic_source_primary,
        page_goal=req.page_goal,
        primary_metric=req.primary_metric,
        business_constraints=req.business_constraints,
    )
    return CreateContextResponse(**result)


@router.get(
    "/{context_id}",
    response_model=dict[str, Any],
    dependencies=[Depends(require_internal_key)],
)
async def read_context(
    context_id: int,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ctx = await get_context(session=session, context_id=context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Marketing context not found")
    return ctx


@router.post(
    "/{context_id}/approve",
    response_model=ApproveResponse,
    dependencies=[Depends(require_internal_key)],
)
async def approve(
    context_id: int,
    session: AsyncSession = Depends(get_db),
) -> ApproveResponse:
    ctx = await get_context(session=session, context_id=context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Marketing context not found")
    await approve_context(session=session, context_id=context_id)
    return ApproveResponse(context_id=context_id, status="approved")
