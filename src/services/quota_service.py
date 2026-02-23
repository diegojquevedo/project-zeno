from datetime import date
from typing import Optional

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import APISettings
from src.core.constants import ANONYMOUS_USER_PREFIX, NEXTJS_IP_HEADER
from src.models import DailyUsageOrm, UserType
from src.schemas import UserModel


class QuotaService:
    """Service for quota checking and enforcement."""

    @staticmethod
    async def extract_anonymous_session_cookie(request: Request) -> str:
        """Extract the anonymous session cookie from request headers."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return f"{ANONYMOUS_USER_PREFIX}:no-session"
        credentials = auth_header.replace("Bearer ", "", 1)
        parts = credentials.split(":", 1)
        if len(parts) == 2:
            return f"{ANONYMOUS_USER_PREFIX}:{parts[1]}"
        return f"{ANONYMOUS_USER_PREFIX}:no-session"

    @staticmethod
    async def get_user_identity_and_daily_quota(
        request: Request,
        user: Optional[UserModel],
    ) -> dict:
        """Determine user identity and daily prompt quota."""
        if not user:
            return {
                "identity": await QuotaService.extract_anonymous_session_cookie(
                    request
                ),
                "prompt_quota": APISettings.anonymous_user_daily_quota,
            }
        if user.user_type == UserType.ADMIN:
            daily_quota = APISettings.admin_user_daily_quota
        elif user.user_type == UserType.MACHINE:
            daily_quota = APISettings.machine_user_daily_quota
        elif user.user_type == UserType.PRO:
            daily_quota = APISettings.pro_user_daily_quota
        else:
            daily_quota = APISettings.regular_user_daily_quota
        return {"identity": f"user:{user.id}", "prompt_quota": daily_quota}

    @staticmethod
    async def check_quota(
        request: Request,
        user: Optional[UserModel],
        session: AsyncSession,
    ) -> dict:
        """Check current daily usage quota (does not increment)."""
        if not APISettings.enable_quota_checking:
            return {}

        identity_and_quota = await QuotaService.get_user_identity_and_daily_quota(
            request, user
        )
        today = date.today()

        stmt = select(DailyUsageOrm).filter_by(
            id=identity_and_quota["identity"], date=today
        )
        result = await session.execute(stmt)
        daily_usage = result.scalars().first()

        identity_and_quota["prompts_used"] = (
            daily_usage.usage_count if daily_usage else 0
        )
        return identity_and_quota

    @staticmethod
    async def enforce_quota(
        request: Request,
        user: Optional[UserModel],
        session: AsyncSession,
    ) -> dict:
        """Enforce daily usage quota, increment usage. Raises HTTPException 429 if exceeded."""
        from fastapi import HTTPException

        if not APISettings.enable_quota_checking:
            return {}

        identity_and_quota = await QuotaService.get_user_identity_and_daily_quota(
            request, user
        )
        user_is_anonymous = (
            identity_and_quota["identity"].split(":")[0] == ANONYMOUS_USER_PREFIX
        )
        anonymous_user_ip = None
        if user_is_anonymous:
            anonymous_user_ip = request.headers.get(NEXTJS_IP_HEADER)

        today = date.today()
        stmt = (
            insert(DailyUsageOrm)
            .values(
                id=identity_and_quota["identity"],
                date=today,
                usage_count=1,
                ip_address=anonymous_user_ip,
            )
            .on_conflict_do_update(
                index_elements=["id", "date"],
                set_={"usage_count": DailyUsageOrm.usage_count + 1},
            )
            .returning(DailyUsageOrm.usage_count)
        )
        result = await session.execute(stmt)
        count = result.scalars().first()
        await session.commit()

        if count and count > identity_and_quota["prompt_quota"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily free limit of {identity_and_quota['prompt_quota']} exceeded; please try again tomorrow.",
            )

        identity_and_quota["prompts_used"] = count

        if user_is_anonymous and anonymous_user_ip:
            stmt = select(func.sum(DailyUsageOrm.usage_count)).filter_by(
                date=today, ip_address=anonymous_user_ip
            )
            result = await session.execute(stmt)
            ip_count = result.scalar() or 0
            if ip_count and ip_count > APISettings.ip_address_daily_quota:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily free limit of {APISettings.ip_address_daily_quota} exceeded for IP address",
                )

        return identity_and_quota
