from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    check_quota,
    get_session_from_pool_dependency,
    optional_auth,
)
from src.schemas import QuotaModel, UserModel

router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("", response_model=QuotaModel)
async def get_quota(
    request: Request,
    user: Optional[UserModel] = Depends(optional_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Get current quota usage."""
    quota_info = await check_quota(request, user, session)
    return quota_info
