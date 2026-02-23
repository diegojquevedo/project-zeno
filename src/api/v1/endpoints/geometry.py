from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import optional_auth
from src.schemas import GeometryResponse, UserModel
from src.shared.geocoding_helpers import get_geometry_data
from src.shared.logging_config import get_logger

router = APIRouter(prefix="/geometry", tags=["geometry"])
logger = get_logger(__name__)


@router.get("/{source}/{src_id}", response_model=GeometryResponse)
async def get_geometry(
    source: str,
    src_id: str,
    user: Optional[UserModel] = Depends(optional_auth),
):
    """Get geometry data by source and source ID."""
    try:
        result = await get_geometry_data(source, src_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Geometry not found for source '{source}' with ID {src_id}",
            )
        return GeometryResponse(**result)
    except ValueError as e:
        logger.exception("Error fetching geometry for %s:%s", source, src_id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error fetching geometry for %s:%s", source, src_id)
        raise HTTPException(status_code=500, detail=str(e))
