from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_session_from_pool_dependency, require_auth
from src.schemas import (
    CustomAreaCreate,
    CustomAreaModel,
    CustomAreaNameRequest,
    UserModel,
)
from src.services.custom_area_service import CustomAreaService
from src.shared.logging_config import get_logger

router = APIRouter(prefix="/custom_areas", tags=["custom_areas"])
logger = get_logger(__name__)


@router.post("/name")
async def custom_area_name(
    request: CustomAreaNameRequest,
    user: UserModel = Depends(require_auth),
):
    """Generate a neutral geographic name for GeoJSON features."""
    try:
        name = await CustomAreaService.generate_area_name(request.features)
        return {"name": name}
    except Exception as e:
        logger.exception("Error generating area name: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=CustomAreaModel)
async def create_custom_area(
    area: CustomAreaCreate,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Create a new custom area for the authenticated user."""
    return await CustomAreaService.create_custom_area(user.id, area, session)


@router.get("", response_model=list[CustomAreaModel])
async def list_custom_areas(
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """List all custom areas belonging to the authenticated user."""
    return await CustomAreaService.list_custom_areas(user.id, session)


@router.get("/{area_id}", response_model=CustomAreaModel)
async def get_custom_area(
    area_id: UUID,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Get a specific custom area by ID."""
    return await CustomAreaService.get_custom_area(area_id, user.id, session)


@router.patch("/{area_id}", response_model=CustomAreaModel)
async def update_custom_area_name(
    area_id: UUID,
    payload: dict,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Update the name of a custom area."""
    name = payload.get("name")
    if name is None:
        raise HTTPException(status_code=400, detail="name field required")
    return await CustomAreaService.update_custom_area_name(
        area_id, user.id, name, session
    )


@router.delete("/{area_id}", status_code=204)
async def delete_custom_area(
    area_id: UUID,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Delete a custom area."""
    await CustomAreaService.delete_custom_area(area_id, user.id, session)
    return None
