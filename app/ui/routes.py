"""UI routes — HTML pages served via Jinja2 templates with HTMX.

Provides:
  GET /                                    — Dashboard
  GET /partitions/{partition_id}           — Partition detail
  GET /partitions-partial                  — HTMX polling partial for dashboard
  GET /ui/partitions/{id}/detail-partial   — HTMX polling partial for detail page
  POST /ui/partitions/{id}/disarm-row      — Disarm, return dashboard row
  POST /ui/partitions/{id}/arm-row         — Arm, return dashboard row
  POST /ui/partitions/{id}/disarm-detail   — Disarm, return detail body
  POST /ui/partitions/{id}/arm-detail      — Arm, return detail body
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.partitions.service import (
    arm_partition,
    disarm_partition,
    get_dashboard,
    get_partition_audit_log,
    get_partition_detail,
    get_partition_state,
)

templates = Jinja2Templates(directory="app/templates")

ui_router = APIRouter(tags=["ui"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@ui_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    dashboard_data = await get_dashboard(db)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "dashboard_data": dashboard_data},
    )


@ui_router.get("/partitions-partial", response_class=HTMLResponse)
async def partitions_partial(request: Request, db: AsyncSession = Depends(get_db)):
    dashboard_data = await get_dashboard(db)
    return templates.TemplateResponse(
        "partials/partition_rows.html",
        {"request": request, "partitions": dashboard_data.partitions},
    )


# ---------------------------------------------------------------------------
# Partition detail
# ---------------------------------------------------------------------------


@ui_router.get("/partitions/{partition_id}", response_class=HTMLResponse)
async def partition_detail(
    partition_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException

    try:
        partition = await get_partition_detail(partition_id, db)
    except HTTPException as exc:
        if exc.status_code == 404:
            return templates.TemplateResponse(
                "404.html",
                {"request": request},
                status_code=404,
            )
        raise

    state = await get_partition_state(partition_id, db)
    audit = await get_partition_audit_log(partition_id, 20, 0, db)

    rearm_in_minutes = None
    if state.scheduled_rearm_at:
        delta = (state.scheduled_rearm_at - datetime.now(timezone.utc)).total_seconds()
        rearm_in_minutes = max(0, int(delta // 60))

    return templates.TemplateResponse(
        "partition_detail.html",
        {
            "request": request,
            "partition": partition,
            "state": state,
            "audit": audit,
            "rearm_in_minutes": rearm_in_minutes,
        },
    )


@ui_router.get("/ui/partitions/{partition_id}/detail-partial", response_class=HTMLResponse)
async def partition_detail_partial(
    partition_id: uuid.UUID,
    request: Request,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    state = await get_partition_state(partition_id, db)
    audit = await get_partition_audit_log(partition_id, 20, offset, db)

    rearm_in_minutes = None
    if state.scheduled_rearm_at:
        delta = (state.scheduled_rearm_at - datetime.now(timezone.utc)).total_seconds()
        rearm_in_minutes = max(0, int(delta // 60))

    return templates.TemplateResponse(
        "partials/partition_detail_body.html",
        {
            "request": request,
            "state": state,
            "audit": audit,
            "rearm_in_minutes": rearm_in_minutes,
            "partition_id": str(partition_id),
        },
    )


# ---------------------------------------------------------------------------
# ARM / DISARM — dashboard row variants
# ---------------------------------------------------------------------------


@ui_router.post("/ui/partitions/{partition_id}/disarm-row", response_class=HTMLResponse)
async def disarm_row(
    partition_id: uuid.UUID,
    request: Request,
    disarmed_by: str = Form("operator"),
    reason: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    await disarm_partition(partition_id, disarmed_by, reason, db)
    dashboard_data = await get_dashboard(db)
    matching = next((p for p in dashboard_data.partitions if p.id == partition_id), None)
    return templates.TemplateResponse(
        "partials/partition_row_single.html",
        {"request": request, "p": matching},
    )


@ui_router.post("/ui/partitions/{partition_id}/arm-row", response_class=HTMLResponse)
async def arm_row(
    partition_id: uuid.UUID,
    request: Request,
    armed_by: str = Form("operator"),
    db: AsyncSession = Depends(get_db),
):
    await arm_partition(partition_id, armed_by, db)
    dashboard_data = await get_dashboard(db)
    matching = next((p for p in dashboard_data.partitions if p.id == partition_id), None)
    return templates.TemplateResponse(
        "partials/partition_row_single.html",
        {"request": request, "p": matching},
    )


# ---------------------------------------------------------------------------
# ARM / DISARM — detail body variants
# ---------------------------------------------------------------------------


@ui_router.post("/ui/partitions/{partition_id}/disarm-detail", response_class=HTMLResponse)
async def disarm_detail(
    partition_id: uuid.UUID,
    request: Request,
    disarmed_by: str = Form("operator"),
    reason: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    await disarm_partition(partition_id, disarmed_by, reason, db)
    state = await get_partition_state(partition_id, db)
    audit = await get_partition_audit_log(partition_id, 20, 0, db)

    rearm_in_minutes = None
    if state.scheduled_rearm_at:
        delta = (state.scheduled_rearm_at - datetime.now(timezone.utc)).total_seconds()
        rearm_in_minutes = max(0, int(delta // 60))

    return templates.TemplateResponse(
        "partials/partition_detail_body.html",
        {
            "request": request,
            "state": state,
            "audit": audit,
            "rearm_in_minutes": rearm_in_minutes,
            "partition_id": str(partition_id),
        },
    )


@ui_router.post("/ui/partitions/{partition_id}/arm-detail", response_class=HTMLResponse)
async def arm_detail(
    partition_id: uuid.UUID,
    request: Request,
    armed_by: str = Form("operator"),
    db: AsyncSession = Depends(get_db),
):
    await arm_partition(partition_id, armed_by, db)
    state = await get_partition_state(partition_id, db)
    audit = await get_partition_audit_log(partition_id, 20, 0, db)

    rearm_in_minutes = None
    if state.scheduled_rearm_at:
        delta = (state.scheduled_rearm_at - datetime.now(timezone.utc)).total_seconds()
        rearm_in_minutes = max(0, int(delta // 60))

    return templates.TemplateResponse(
        "partials/partition_detail_body.html",
        {
            "request": request,
            "state": state,
            "audit": audit,
            "rearm_in_minutes": rearm_in_minutes,
            "partition_id": str(partition_id),
        },
    )
