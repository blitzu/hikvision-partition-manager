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
  GET /partitions/new                      — Partition create form
  GET /partitions/{id}/edit                — Partition edit form
  POST /ui/partitions/create               — Handle create form submission
  POST /ui/partitions/{id}/update          — Handle edit form submission
  GET /ui/nvrs/{id}/cameras                — DB-only camera list partial
  GET /ui/nvrs/{id}/cameras/sync           — Sync cameras then return partial
  GET /nvrs                                — NVR management page
  GET /ui/nvrs/{id}/detail                 — Expandable camera list partial
  GET /ui/nvrs/{id}/test                   — Inline connectivity test result
  POST /ui/nvrs/create                     — Add NVR form submission
"""
import uuid
from datetime import datetime, timezone
from typing import List

import httpx
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cameras.models import Camera
from app.core.database import get_db
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.partitions.schemas import PartitionCreate, PartitionUpdate
from app.partitions.service import (
    arm_partition,
    create_partition,
    disarm_partition,
    get_dashboard,
    get_partition_audit_log,
    get_partition_detail,
    get_partition_state,
    sync_partition_cameras,
    update_partition,
)

templates = Jinja2Templates(directory="app/templates")

ui_router = APIRouter(tags=["ui"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_nvrs_with_cameras(db: AsyncSession) -> List[dict]:
    """Return list of {nvr, cameras} dicts for the camera selector."""
    result = await db.execute(select(NVRDevice))
    nvrs = result.scalars().all()
    out = []
    for nvr in nvrs:
        cam_result = await db.execute(select(Camera).where(Camera.nvr_id == nvr.id))
        cameras = cam_result.scalars().all()
        out.append({"nvr": nvr, "cameras": cameras})
    return out


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


# ---------------------------------------------------------------------------
# Partition create / edit form
# ---------------------------------------------------------------------------


@ui_router.get("/partitions/new", response_class=HTMLResponse)
async def partition_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    nvr_sections = await _get_nvrs_with_cameras(db)
    return templates.TemplateResponse(
        "partition_form.html",
        {
            "request": request,
            "partition": None,
            "nvr_sections": nvr_sections,
            "mode": "create",
            "selected_camera_ids": set(),
            "error": None,
        },
    )


@ui_router.get("/partitions/{partition_id}/edit", response_class=HTMLResponse)
async def partition_edit_form(
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

    nvr_sections = await _get_nvrs_with_cameras(db)
    selected_ids = {c.id for c in partition.cameras}
    return templates.TemplateResponse(
        "partition_form.html",
        {
            "request": request,
            "partition": partition,
            "nvr_sections": nvr_sections,
            "mode": "edit",
            "selected_camera_ids": selected_ids,
            "error": None,
        },
    )


@ui_router.post("/ui/partitions/create", response_class=HTMLResponse)
async def partition_create_submit(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    auto_rearm_minutes: int = Form(None),
    alert_if_disarmed_minutes: int = Form(None),
    camera_ids: List[uuid.UUID] = Form(default=[]),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await create_partition(
            PartitionCreate(
                name=name,
                description=description,
                auto_rearm_minutes=auto_rearm_minutes,
                alert_if_disarmed_minutes=alert_if_disarmed_minutes,
                camera_ids=camera_ids,
            ),
            db,
        )
        return RedirectResponse(url=f"/partitions/{result.id}", status_code=303)
    except Exception as exc:
        nvr_sections = await _get_nvrs_with_cameras(db)
        return templates.TemplateResponse(
            "partition_form.html",
            {
                "request": request,
                "partition": None,
                "nvr_sections": nvr_sections,
                "mode": "create",
                "selected_camera_ids": set(camera_ids),
                "error": str(exc),
            },
        )


@ui_router.post("/ui/partitions/{partition_id}/update", response_class=HTMLResponse)
async def partition_update_submit(
    partition_id: uuid.UUID,
    request: Request,
    name: str = Form(None),
    description: str = Form(None),
    auto_rearm_minutes: int = Form(None),
    alert_if_disarmed_minutes: int = Form(None),
    camera_ids: List[uuid.UUID] = Form(default=[]),
    db: AsyncSession = Depends(get_db),
):
    try:
        await update_partition(
            partition_id,
            PartitionUpdate(
                name=name,
                description=description,
                auto_rearm_minutes=auto_rearm_minutes,
                alert_if_disarmed_minutes=alert_if_disarmed_minutes,
            ),
            db,
        )
        await sync_partition_cameras(partition_id, camera_ids, db)
        return RedirectResponse(url=f"/partitions/{partition_id}", status_code=303)
    except Exception as exc:
        from fastapi import HTTPException

        try:
            partition = await get_partition_detail(partition_id, db)
        except HTTPException:
            partition = None
        nvr_sections = await _get_nvrs_with_cameras(db)
        return templates.TemplateResponse(
            "partition_form.html",
            {
                "request": request,
                "partition": partition,
                "nvr_sections": nvr_sections,
                "mode": "edit",
                "selected_camera_ids": set(camera_ids),
                "error": str(exc),
            },
        )


# ---------------------------------------------------------------------------
# Camera section partials (used by partition_form.html Sync button)
# ---------------------------------------------------------------------------


@ui_router.get("/ui/nvrs/{nvr_id}/cameras", response_class=HTMLResponse)
async def nvr_cameras_partial(
    nvr_id: uuid.UUID,
    selected: str = Query(default=""),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    nvr = await db.get(NVRDevice, nvr_id)
    cam_result = await db.execute(select(Camera).where(Camera.nvr_id == nvr_id))
    cameras = cam_result.scalars().all()
    selected_ids = {uuid.UUID(s) for s in selected.split(",") if s}
    return templates.TemplateResponse(
        "partials/nvr_camera_section.html",
        {"request": request, "nvr": nvr, "cameras": cameras, "selected_camera_ids": selected_ids},
    )


@ui_router.get("/ui/nvrs/{nvr_id}/cameras/sync", response_class=HTMLResponse)
async def nvr_cameras_sync_partial(
    nvr_id: uuid.UUID,
    selected: str = Query(default=""),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        try:
            await client.get(f"http://localhost:8000/api/nvrs/{nvr_id}/cameras/sync", timeout=15.0)
        except Exception:
            pass  # Best-effort sync; fall through to DB query
    nvr = await db.get(NVRDevice, nvr_id)
    cam_result = await db.execute(select(Camera).where(Camera.nvr_id == nvr_id))
    cameras = cam_result.scalars().all()
    selected_ids = {uuid.UUID(s) for s in selected.split(",") if s}
    return templates.TemplateResponse(
        "partials/nvr_camera_section.html",
        {"request": request, "nvr": nvr, "cameras": cameras, "selected_camera_ids": selected_ids},
    )


# ---------------------------------------------------------------------------
# NVR management page
# ---------------------------------------------------------------------------


@ui_router.get("/nvrs", response_class=HTMLResponse)
async def nvrs_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    nvr_result = await db.execute(select(NVRDevice))
    nvrs = nvr_result.scalars().all()
    loc_result = await db.execute(select(Location))
    locations = loc_result.scalars().all()
    return templates.TemplateResponse(
        "nvrs.html",
        {"request": request, "nvrs": nvrs, "locations": locations, "error": None},
    )


@ui_router.get("/ui/nvrs/{nvr_id}/detail", response_class=HTMLResponse)
async def nvr_detail_partial(
    nvr_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    nvr = await db.get(NVRDevice, nvr_id)
    cam_result = await db.execute(select(Camera).where(Camera.nvr_id == nvr_id))
    cameras = cam_result.scalars().all()
    return templates.TemplateResponse(
        "partials/nvr_detail_section.html",
        {"request": request, "nvr": nvr, "cameras": cameras},
    )


@ui_router.get("/ui/nvrs/{nvr_id}/test", response_class=HTMLResponse)
async def nvr_test_connectivity(
    nvr_id: uuid.UUID,
):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"http://localhost:8000/api/nvrs/{nvr_id}/test", timeout=15.0)
            data = resp.json()
        except Exception as exc:
            return HTMLResponse(f'<span style="color:red">Error — {exc}</span>')
    if data.get("success"):
        return HTMLResponse('<span style="color:green">Online ✓</span>')
    else:
        error_msg = data.get("error", "unknown")
        return HTMLResponse(f'<span style="color:red">Offline — {error_msg}</span>')


@ui_router.post("/ui/nvrs/create", response_class=HTMLResponse)
async def nvr_create_submit(
    request: Request,
    location_id: uuid.UUID = Form(...),
    name: str = Form(...),
    ip_address: str = Form(...),
    port: int = Form(8000),
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"http://localhost:8000/api/locations/{location_id}/nvrs",
                json={
                    "name": name,
                    "ip_address": ip_address,
                    "port": port,
                    "username": username,
                    "password": password,
                },
                timeout=15.0,
            )
            data = resp.json()
        except Exception as exc:
            nvr_result = await db.execute(select(NVRDevice))
            nvrs = nvr_result.scalars().all()
            loc_result = await db.execute(select(Location))
            locations = loc_result.scalars().all()
            return templates.TemplateResponse(
                "nvrs.html",
                {"request": request, "nvrs": nvrs, "locations": locations, "error": str(exc)},
            )

    if data.get("success"):
        return RedirectResponse(url="/nvrs", status_code=303)
    else:
        nvr_result = await db.execute(select(NVRDevice))
        nvrs = nvr_result.scalars().all()
        loc_result = await db.execute(select(Location))
        locations = loc_result.scalars().all()
        return templates.TemplateResponse(
            "nvrs.html",
            {
                "request": request,
                "nvrs": nvrs,
                "locations": locations,
                "error": data.get("error", "Failed to create NVR"),
            },
        )
