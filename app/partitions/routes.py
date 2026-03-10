import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import APIResponse
from app.partitions.schemas import (
    DisarmRequest,
    DisarmResponse,
    ArmRequest,
    ArmResponse,
    PartitionCreate,
    PartitionUpdate,
    PartitionRead,
    PartitionDetail,
    PartitionCameraSync,
    PartitionStateRead,
    PaginatedAuditLog,
    DashboardResponse,
)
from app.partitions.service import (
    disarm_partition,
    arm_partition,
    create_partition,
    get_partitions,
    get_partition_detail,
    update_partition,
    sync_partition_cameras,
    delete_partition,
    get_partition_state,
    get_partition_audit_log,
    get_dashboard,
)

router = APIRouter(prefix="/api/partitions", tags=["partitions"])
dashboard_router = APIRouter(prefix="/api", tags=["dashboard"])

# ---------------------------------------------------------------------------
# Dashboard endpoint
# ---------------------------------------------------------------------------

@dashboard_router.get("/dashboard", response_model=APIResponse[DashboardResponse])
async def get_dashboard_endpoint(
    db: AsyncSession = Depends(get_db),
):
    """Aggregated dashboard: all partitions with disarmed duration, overdue flag.

    Partitions in active states (error / partial / disarmed) are sorted first.
    """
    try:
        result = await get_dashboard(db)
        return APIResponse(success=True, data=result)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ---------------------------------------------------------------------------
# Arm / Disarm endpoints (pre-existing)
# ---------------------------------------------------------------------------

@router.post("/{partition_id}/disarm", response_model=APIResponse[DisarmResponse])
async def disarm(
    partition_id: uuid.UUID,
    body: DisarmRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await disarm_partition(partition_id, body.disarmed_by, body.reason, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))

@router.post("/{partition_id}/arm", response_model=APIResponse[ArmResponse])
async def arm(
    partition_id: uuid.UUID,
    body: ArmRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await arm_partition(partition_id, body.armed_by, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))

# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=APIResponse[PartitionRead])
async def create(
    body: PartitionCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await create_partition(body, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("", response_model=APIResponse[list[PartitionRead]])
async def list_partitions(
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await get_partitions(db)
        return APIResponse(success=True, data=result)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/{partition_id}", response_model=APIResponse[PartitionDetail])
async def get_one(
    partition_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await get_partition_detail(partition_id, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.patch("/{partition_id}", response_model=APIResponse[PartitionRead])
async def update(
    partition_id: uuid.UUID,
    body: PartitionUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await update_partition(partition_id, body, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.delete("/{partition_id}", response_model=APIResponse[None])
async def soft_delete(
    partition_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_partition(partition_id, db)
        return APIResponse(success=True)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.put("/{partition_id}/cameras", response_model=APIResponse[PartitionDetail])
async def sync_cameras(
    partition_id: uuid.UUID,
    body: PartitionCameraSync,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await sync_partition_cameras(partition_id, body.camera_ids, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/{partition_id}/state", response_model=APIResponse[PartitionStateRead])
async def get_state(
    partition_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Deep-dive into why a partition is in its current state (per-camera status and refcounts)."""
    try:
        result = await get_partition_state(partition_id, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/{partition_id}/audit", response_model=APIResponse[PaginatedAuditLog])
async def get_audit(
    partition_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Paginated audit log for a partition. Supports limit and offset query parameters."""
    try:
        result = await get_partition_audit_log(partition_id, limit, offset, db)
        return APIResponse(success=True, data=result)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    except Exception as e:
        return APIResponse(success=False, error=str(e))
