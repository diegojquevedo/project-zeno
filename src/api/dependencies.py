import json
from typing import Optional

import cachetools
import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import fetch_checkpointer  # noqa: F401
from src.api.auth import MACHINE_USER_PREFIX, validate_machine_user_token
from src.api.config import APISettings
from src.core.constants import (
    ANONYMOUS_USER_PREFIX,
    NEXTJS_API_KEY_HEADER,
    NEXTJS_IP_HEADER,
)
from src.models import UserOrm, WhitelistedUserOrm
from src.schemas import UserModel
from src.shared.database import get_session_from_pool_dependency
from src.shared.logging_config import bind_request_logging_context, get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)

_user_info_cache = cachetools.TTLCache(maxsize=1024, ttl=60 * 60 * 24)


async def is_user_whitelisted(user_email: str, session: AsyncSession) -> bool:
    """Check if user is whitelisted via email or domain."""
    user_email_lower = user_email.lower()
    user_domain = user_email_lower.split("@")[-1]

    stmt = select(WhitelistedUserOrm).where(
        func.lower(WhitelistedUserOrm.email) == user_email_lower
    )
    result = await session.execute(stmt)
    if result.scalars().first():
        return True

    domains = APISettings.domains_allowlist
    if not domains:
        return False
    return user_domain.lower() in [d.lower() for d in domains]


async def is_public_signup_open(session: AsyncSession) -> bool:
    """Check if public signups are allowed and within limits."""
    if not APISettings.allow_public_signups:
        return False
    max_signups = APISettings.max_user_signups
    if max_signups < 0:
        return True
    stmt = select(func.count(UserOrm.id))
    result = await session.execute(stmt)
    current_user_count = result.scalar()
    return current_user_count < max_signups


async def check_signup_limit_allows_new_user(
    user_email: str, session: AsyncSession
) -> bool:
    """Check if signup limits allow a new user to be created."""
    if await is_user_whitelisted(user_email, session):
        return True
    return await is_public_signup_open(session)


async def fetch_user_from_rw_api(
    request: Request,
    authorization: Optional[str] = Depends(security),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
) -> Optional[UserModel]:
    """Fetch user from Resource Watch API or validate machine user token."""
    if not authorization:
        return None

    token = authorization.credentials

    if token and token.startswith(f"{MACHINE_USER_PREFIX}:"):
        return await validate_machine_user_token(token, session)

    if token and token.startswith(f"{ANONYMOUS_USER_PREFIX}:"):
        if request.headers.get(NEXTJS_API_KEY_HEADER) is None or (
            request.headers[NEXTJS_API_KEY_HEADER] != APISettings.nextjs_api_key
        ):
            raise HTTPException(
                status_code=403,
                detail="Invalid API key from NextJS for anonymous user",
            )
        anonymous_user_ip = request.headers.get(NEXTJS_IP_HEADER)
        if anonymous_user_ip is None or anonymous_user_ip.strip() == "":
            raise HTTPException(
                status_code=403,
                detail=f"Missing {NEXTJS_IP_HEADER} header for anonymous user",
            )
        return None

    if token and ":" in token:
        scheme, _ = token.split(":", 1)
        if scheme.lower() != ANONYMOUS_USER_PREFIX:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized, anonymous users should use '{ANONYMOUS_USER_PREFIX}' scheme",
            )

    if token and token in _user_info_cache:
        return _user_info_cache[token]

    from src.infrastructure.external.resource_watch_client import (
        ResourceWatchClient,
    )

    client = ResourceWatchClient(
        auth_url=APISettings.resource_watch_auth_url, timeout=10.0
    )
    try:
        user_info = await client.get_user_info(token)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code, detail=e.response.text
        )
    except Exception as e:
        logger.exception("Error contacting Resource Watch: %s", e)
        raise HTTPException(
            status_code=502, detail=f"Error contacting Resource Watch: {e}"
        )
    if "name" not in user_info:
        logger.warning(
            "User info missing 'name' field, using email as fallback",
            email=user_info.get("email"),
        )
        user_info["name"] = user_info["email"].split("@")[0]

    user_email = user_info["email"]
    if (
        not await is_user_whitelisted(user_email, session)
        and not APISettings.allow_public_signups
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not allowed to access this API",
        )

    user_model = UserModel.model_validate(user_info)
    _user_info_cache[token] = user_model
    return user_model


async def require_auth(
    user_info: Optional[UserModel] = Depends(fetch_user_from_rw_api),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
) -> UserModel:
    """Requires Authorization - raises HTTPException if not authenticated."""
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token in Authorization header",
        )

    stmt = select(UserOrm).filter_by(id=user_info.id)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        if not await check_signup_limit_allows_new_user(user_info.email, session):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User signups are currently closed",
            )
        user = UserOrm(**user_info.model_dump())
        session.add(user)
        await session.commit()
        await session.refresh(user)
    bind_request_logging_context(user_id=user.id)
    return UserModel(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        updated_at=user.updated_at,
        user_type=user.user_type,
        first_name=user.first_name,
        last_name=user.last_name,
        profile_description=user.profile_description,
        sector_code=user.sector_code,
        role_code=user.role_code,
        job_title=user.job_title,
        company_organization=user.company_organization,
        country_code=user.country_code,
        preferred_language_code=user.preferred_language_code,
        gis_expertise_level=user.gis_expertise_level,
        areas_of_interest=user.areas_of_interest,
        topics=json.loads(user.topics) if user.topics else None,
        receive_news_emails=user.receive_news_emails,
        help_test_features=user.help_test_features,
        has_profile=user.has_profile,
    )


async def optional_auth(
    user_info: Optional[UserModel] = Depends(fetch_user_from_rw_api),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
) -> Optional[UserModel]:
    """Optional Authorization - returns None if not authenticated."""
    if not user_info:
        return None

    stmt = select(UserOrm).filter_by(id=user_info.id)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        if not await check_signup_limit_allows_new_user(user_info.email, session):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User signups are currently closed",
            )
        user = UserOrm(**user_info.model_dump())
        session.add(user)
        await session.commit()
        await session.refresh(user)
    bind_request_logging_context(user_id=user.id)
    return UserModel(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        updated_at=user.updated_at,
        user_type=user.user_type,
        first_name=user.first_name,
        last_name=user.last_name,
        profile_description=user.profile_description,
        sector_code=user.sector_code,
        role_code=user.role_code,
        job_title=user.job_title,
        company_organization=user.company_organization,
        country_code=user.country_code,
        preferred_language_code=user.preferred_language_code,
        gis_expertise_level=user.gis_expertise_level,
        areas_of_interest=user.areas_of_interest,
        topics=json.loads(user.topics) if user.topics else None,
        receive_news_emails=user.receive_news_emails,
        help_test_features=user.help_test_features,
        has_profile=user.has_profile,
    )


async def extract_anonymous_session_cookie(request: Request) -> str:
    """Extract the anonymous session cookie from request headers."""
    from src.services.quota_service import QuotaService

    return await QuotaService.extract_anonymous_session_cookie(request)


async def get_user_identity_and_daily_quota(
    request: Request,
    user: Optional[UserModel],
) -> dict:
    """Determine user identity and daily prompt quota."""
    from src.services.quota_service import QuotaService

    return await QuotaService.get_user_identity_and_daily_quota(request, user)


async def check_quota(
    request: Request,
    user: Optional[UserModel],
    session: AsyncSession,
) -> dict:
    """Check current daily usage quota (does not increment)."""
    from src.services.quota_service import QuotaService

    return await QuotaService.check_quota(request, user, session)


async def enforce_quota(
    request: Request,
    user: Optional[UserModel],
    session: AsyncSession,
) -> dict:
    """Enforce daily usage quota, increment usage, raise 429 if exceeded."""
    from src.services.quota_service import QuotaService

    return await QuotaService.enforce_quota(request, user, session)
