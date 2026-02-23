from fastapi import APIRouter

from src.schemas import ProfileConfigResponse

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/config", response_model=ProfileConfigResponse)
async def get_profile_config():
    """Get configuration options for profile dropdowns."""
    return ProfileConfigResponse()
