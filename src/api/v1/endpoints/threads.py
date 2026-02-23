from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response, StreamingResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import fetch_checkpointer
from src.api.dependencies import (
    get_session_from_pool_dependency,
    optional_auth,
    require_auth,
)
from src.schemas import (
    RatingCreateRequest,
    RatingModel,
    ThreadModel,
    ThreadStateResponse,
    ThreadUpdateRequest,
    UserModel,
)
from src.services.thread_service import ThreadService
from src.shared.logging_config import get_logger

router = APIRouter(prefix="/threads", tags=["threads"])
logger = get_logger(__name__)


@router.get("", response_model=list[ThreadModel])
async def list_threads(
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """List all threads belonging to the authenticated user."""
    return await ThreadService.list_threads(user.id, session)


@router.get("/{thread_id}")
async def get_thread(
    thread_id: str,
    user: UserModel | None = Depends(optional_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Get thread conversation history (streaming). Public threads need no auth."""
    try:
        await ThreadService.get_thread_with_access_check(
            thread_id, user, session
        )
        return StreamingResponse(
            ThreadService.stream_thread_replay(thread_id),
            media_type="application/x-ndjson",
        )
    except Exception:
        logger.exception("Replay failed", thread_id=thread_id)
        raise


@router.patch("/{thread_id}", response_model=ThreadModel)
async def update_thread(
    thread_id: str,
    request: ThreadUpdateRequest,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Update thread name and/or visibility."""
    data = request.model_dump(exclude_none=True)
    return await ThreadService.update_thread(
        thread_id, user.id, data, session
    )


@router.get("/{thread_id}/state", response_model=ThreadStateResponse)
async def get_thread_state(
    thread_id: str,
    user: UserModel | None = Depends(optional_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Get current agent state for a thread."""
    try:
        return await ThreadService.get_thread_state(thread_id, user, session)
    except Exception:
        logger.exception("Error retrieving thread state", thread_id=thread_id)
        raise


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    user: UserModel = Depends(require_auth),
    checkpointer: AsyncPostgresSaver = Depends(fetch_checkpointer),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Delete thread permanently."""
    await ThreadService.delete_thread(
        thread_id, user.id, checkpointer, session
    )
    return None


@router.post("/{thread_id}/rating", response_model=RatingModel)
async def create_or_update_rating(
    thread_id: str,
    request: RatingCreateRequest,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Create or update a rating for a trace in a thread."""
    return await ThreadService.create_or_update_rating(
        thread_id, user.id, request, session
    )


@router.get("/{thread_id}/rating", response_model=list[RatingModel])
async def get_thread_ratings(
    thread_id: str,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
):
    """Get all ratings for traces in a thread."""
    return await ThreadService.get_thread_ratings(
        thread_id, user.id, session
    )


@router.get("/{thread_id}/{checkpoint_id}/raw_data")
async def get_raw_data(
    thread_id: str,
    checkpoint_id: str,
    user: UserModel = Depends(require_auth),
    session: AsyncSession = Depends(get_session_from_pool_dependency),
    content_type: str = Header(default="text/csv", alias="Content-Type"),
):
    """Get insights raw data for a thread and checkpoint."""
    raw_data, _ = await ThreadService.get_raw_data(
        thread_id, checkpoint_id, user.id, session
    )
    result = ThreadService.format_raw_data_response(
        raw_data, content_type, thread_id, checkpoint_id
    )

    if result is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=415,
            detail=f"Unsupported Media Type: {content_type}, must be one of [application/json, text/csv]",
        )

    if content_type == "application/json":
        return result

    csv_data, filename = result
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=csv_data, media_type="text/csv", headers=headers
    )
