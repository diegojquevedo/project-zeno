from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import APISettings
from src.api.dependencies import (
    check_quota,
    get_session_from_pool_dependency,
    require_auth,
)
from src.schemas import UserModel, UserProfileUpdateRequest
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def auth_me(
    request: Request,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Get current user with quota info."""
    if not APISettings.enable_quota_checking:
        return {
            **user.model_dump(),
            "prompts_used": None,
            "prompt_quota": None,
        }
    quota_info = await check_quota(request, user, session)
    return {**user.model_dump(), **quota_info}


@router.patch("/profile", response_model=UserModel)
async def update_user_profile(
    profile_update: UserProfileUpdateRequest,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Update user profile fields."""
    return await AuthService.update_user_profile(
        user.id, profile_update, session
    )
