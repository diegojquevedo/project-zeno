import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import APISettings
from src.api.dependencies import (
    enforce_quota,
    get_session_from_pool_dependency,
    optional_auth,
)
from src.api.user_profile_configs.sectors import SECTOR_ROLES, SECTORS
from src.api.v1.streaming import stream_chat
from src.schemas import ChatRequest, UserModel
from src.services.thread_service import ThreadService
from src.shared.logging_config import bind_request_logging_context, get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


@router.post("")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    user: UserModel | None = Depends(optional_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Chat endpoint with quota tracking. Returns streamed NDJSON response."""
    if not user and not APISettings.allow_anonymous_chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous chat access is disabled. Please log in to continue.",
        )

    thread_id = None
    if user:
        bind_request_logging_context(
            thread_id=chat_request.thread_id,
            session_id=chat_request.session_id,
            query=chat_request.query,
        )
        thread_id, _ = await ThreadService.ensure_thread_for_chat(
            chat_request.thread_id, user.id, chat_request.query, session
        )
    if thread_id is None:
        thread_id = chat_request.thread_id

    trace_id = str(uuid.uuid4())

    try:
        quota_info = await enforce_quota(request, user, session)

        headers = {}
        if APISettings.enable_quota_checking and quota_info:
            headers["X-Prompts-Used"] = str(quota_info["prompts_used"])
            headers["X-Prompts-Quota"] = str(quota_info["prompt_quota"])

        user_dict = None
        if user:
            user_dict = {
                "country_code": user.country_code,
                "preferred_language_code": user.preferred_language_code,
                "areas_of_interest": user.areas_of_interest,
            }
            if user.sector_code and user.sector_code in SECTORS:
                user_dict["sector_code"] = SECTORS[user.sector_code]
                if user.role_code and user.role_code in SECTOR_ROLES.get(
                    user.sector_code, {}
                ):
                    user_dict["role_code"] = SECTOR_ROLES[user.sector_code][
                        user.role_code
                    ]

        return StreamingResponse(
            stream_chat(
                query=chat_request.query,
                user_persona=chat_request.user_persona,
                thread_id=thread_id,
                ui_context=chat_request.ui_context,
                ui_action_only=chat_request.ui_action_only,
                trace_id=trace_id,
                user=user_dict,
            ),
            media_type="application/x-ndjson",
            headers=headers if headers else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Chat request failed",
            error=str(e),
            error_type=type(e).__name__,
            thread_id=chat_request.thread_id,
        )
        raise HTTPException(status_code=500, detail=str(e))
