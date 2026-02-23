import io
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd
from langchain_core.load import dumps
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import fetch_zeno
from src.agents.llms import SMALL_MODEL
from src.api.v1.streaming import replay_chat
from src.core.exceptions import ResourceNotFoundError
from src.models import RatingOrm, ThreadOrm, UserType
from src.schemas import (
    RatingCreateRequest,
    RatingModel,
    ThreadModel,
    ThreadNameOutput,
    ThreadStateResponse,
    UserModel,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


class ThreadService:
    """Service for thread, rating, and raw data operations."""

    @staticmethod
    async def list_threads(
        user_id: str,
        session: AsyncSession,
    ) -> list[ThreadModel]:
        """List all threads belonging to the user."""
        stmt = select(ThreadOrm).filter_by(user_id=user_id)
        result = await session.execute(stmt)
        threads = result.scalars().all()
        return [ThreadModel.model_validate(t) for t in threads]

    @staticmethod
    async def get_thread_with_access_check(
        thread_id: str,
        user: Optional[UserModel],
        session: AsyncSession,
    ) -> ThreadOrm:
        """Get thread and verify access. Public threads need no auth; private require user."""
        stmt = select(ThreadOrm).filter_by(id=thread_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()

        if not thread:
            raise ResourceNotFoundError("Thread not found")

        if not thread.is_public:
            if not user:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing Bearer token",
                )
            if thread.user_id != user.id and user.user_type != UserType.ADMIN:
                raise ResourceNotFoundError("Thread not found")

        return thread

    @staticmethod
    async def stream_thread_replay(thread_id: str):
        """Stream chat replay for a thread."""
        return replay_chat(thread_id=thread_id)

    @staticmethod
    async def update_thread(
        thread_id: str,
        user_id: str,
        data: dict,
        session: AsyncSession,
    ) -> ThreadModel:
        """Update thread name and/or visibility."""
        stmt = select(ThreadOrm).filter_by(user_id=user_id, id=thread_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()
        if not thread:
            raise ResourceNotFoundError("Thread not found")

        for key, value in data.items():
            if value is not None:
                setattr(thread, key, value)
        await session.commit()
        await session.refresh(thread)
        return ThreadModel.model_validate(thread)

    @staticmethod
    async def get_thread_state(
        thread_id: str,
        user: Optional[UserModel],
        session: AsyncSession,
    ) -> ThreadStateResponse:
        """Get current agent state for a thread."""
        await ThreadService.get_thread_with_access_check(
            thread_id, user, session
        )
        zeno_async = await fetch_zeno()
        config = {"configurable": {"thread_id": thread_id}}
        state = await zeno_async.aget_state(config=config)
        return ThreadStateResponse(
            thread_id=thread_id,
            state=dumps(state.values),
        )

    @staticmethod
    async def delete_thread(
        thread_id: str,
        user_id: str,
        checkpointer: AsyncPostgresSaver,
        session: AsyncSession,
    ) -> None:
        """Delete thread permanently."""
        await checkpointer.adelete_thread(thread_id)
        stmt = select(ThreadOrm).filter_by(user_id=user_id, id=thread_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()
        if not thread:
            raise ResourceNotFoundError("Thread not found")
        await session.delete(thread)
        await session.commit()

    @staticmethod
    async def create_or_update_rating(
        thread_id: str,
        user_id: str,
        request: RatingCreateRequest,
        session: AsyncSession,
    ) -> RatingModel:
        """Create or update a rating for a trace in a thread."""
        stmt = select(ThreadOrm).filter_by(id=thread_id, user_id=user_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()
        if not thread:
            raise ResourceNotFoundError("Thread not found or access denied")

        stmt = select(RatingOrm).filter_by(
            user_id=user_id,
            thread_id=thread_id,
            trace_id=request.trace_id,
        )
        result = await session.execute(stmt)
        existing_rating = result.scalars().first()

        if existing_rating:
            existing_rating.rating = request.rating
            existing_rating.comment = request.comment
            existing_rating.updated_at = datetime.now()
            await session.commit()
            await session.refresh(existing_rating)
            logger.info(
                "Rating updated",
                user_id=user_id,
                thread_id=thread_id,
                trace_id=request.trace_id,
                rating=request.rating,
                comment=request.comment,
            )
            return RatingModel.model_validate(existing_rating)

        new_rating = RatingOrm(
            id=str(uuid.uuid4()),
            user_id=user_id,
            thread_id=thread_id,
            trace_id=request.trace_id,
            rating=request.rating,
            comment=request.comment,
        )
        session.add(new_rating)
        await session.commit()
        await session.refresh(new_rating)
        logger.info(
            "Rating created",
            user_id=user_id,
            thread_id=thread_id,
            trace_id=request.trace_id,
            rating=request.rating,
            comment=request.comment,
        )
        return RatingModel.model_validate(new_rating)

    @staticmethod
    async def get_thread_ratings(
        thread_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> list[RatingModel]:
        """Get all ratings for traces in a thread."""
        stmt = select(ThreadOrm).filter_by(id=thread_id, user_id=user_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()
        if not thread:
            raise ResourceNotFoundError("Thread not found or access denied")

        stmt = (
            select(RatingOrm)
            .filter_by(user_id=user_id, thread_id=thread_id)
            .order_by(RatingOrm.created_at)
        )
        result = await session.execute(stmt)
        ratings = result.scalars().all()
        return [RatingModel.model_validate(r) for r in ratings]

    @staticmethod
    async def get_raw_data(
        thread_id: str,
        checkpoint_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> tuple[dict, ThreadOrm]:
        """Get raw_data from thread checkpoint state. Returns (raw_data dict, thread)."""
        stmt = select(ThreadOrm).filter_by(id=thread_id, user_id=user_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()
        if not thread:
            raise ResourceNotFoundError(f"Thread id: {thread_id} not found")

        zeno_async = await fetch_zeno()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        state = await zeno_async.aget_state(config=config)
        raw_data = state.values.get("raw_data", {})
        return raw_data, thread

    @staticmethod
    def format_raw_data_response(
        raw_data: dict,
        content_type: str,
        thread_id: str,
        checkpoint_id: str,
    ):
        """Format raw_data as CSV or JSON response."""
        df = pd.DataFrame(raw_data)

        if "id" in df.columns:
            cols = ["id"] + [c for c in df.columns if c != "id"]
            df = df[cols]

        if content_type == "application/json":
            return df.to_dict()

        if content_type == "text/csv":
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            csv_data = buf.getvalue()
            filename = f"thread_{thread_id}_checkpoint_{checkpoint_id}_raw_data.csv"
            return csv_data, filename

        return None

    @staticmethod
    async def generate_thread_name(query: str) -> str:
        """Generate a descriptive name for a chat thread based on the query."""
        try:
            prompt = f"""Generate a concise, descriptive title (max 50 chars) for a chat conversation that starts with this query:

        QUERY:
        {query}

        CONTEXT:
        Current date is {datetime.now().strftime("%Y-%m-%d")}. Use this for relative time queries like "past 3 months", "last week", etc.
        """
            response = await SMALL_MODEL.with_structured_output(
                ThreadNameOutput
            ).ainvoke(prompt)
            name = response.name
            if len(name) > 50:
                return name[:47] + "..."
            return name
        except Exception as e:
            logger.exception("Error generating thread name: %s", e)
            return "Unnamed Thread"

    @staticmethod
    async def ensure_thread_for_chat(
        thread_id: Optional[str],
        user_id: Optional[str],
        query: str,
        session: AsyncSession,
    ) -> tuple[Optional[str], Optional[ThreadOrm]]:
        """Ensure thread exists for chat. Create if needed. Returns (thread_id, thread)."""
        if not user_id:
            return thread_id, None

        if not thread_id:
            return None, None

        stmt = select(ThreadOrm).filter_by(id=thread_id, user_id=user_id)
        result = await session.execute(stmt)
        thread = result.scalars().first()

        if not thread:
            thread_name = await ThreadService.generate_thread_name(query)
            thread = ThreadOrm(
                id=thread_id,
                user_id=user_id,
                agent_id="GEOAI",
                name=thread_name,
            )
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

        return thread_id, thread
