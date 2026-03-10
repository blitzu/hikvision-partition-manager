"""Location CRUD API routes.

Endpoints:
  POST /api/locations        — create a location
  GET  /api/locations        — list all locations (ordered by name)
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import APIResponse
from app.locations.models import Location
from app.locations.schemas import LocationCreate, LocationRead

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.post("", response_model=APIResponse[LocationRead])
async def create_location(
    body: LocationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[LocationRead]:
    """Create a new location."""
    try:
        location = Location(name=body.name, timezone=body.timezone)
        db.add(location)
        await db.commit()
        return APIResponse(success=True, data=LocationRead.model_validate(location))
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("", response_model=APIResponse[list[LocationRead]])
async def list_locations(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[list[LocationRead]]:
    """List all locations ordered by name."""
    try:
        result = await db.execute(select(Location).order_by(Location.name))
        locations = result.scalars().all()
        return APIResponse(
            success=True,
            data=[LocationRead.model_validate(loc) for loc in locations],
        )
    except Exception as e:
        return APIResponse(success=False, error=str(e))
