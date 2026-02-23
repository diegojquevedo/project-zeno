from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ThreadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    agent_id: str
    name: str
    is_public: bool
    created_at: datetime
    updated_at: datetime


class ThreadNameOutput(BaseModel):
    name: str = Field(
        ...,
        description="Generated name for thread",
        max_length=50,
    )

    @field_validator("name", mode="before")
    def truncate_thread_name(cls, value):
        if isinstance(value, str) and len(value) > 50:
            return value[:50]
        return value


class ThreadStateResponse(BaseModel):
    """Response model for thread state endpoint."""

    thread_id: str
    state: str = Field(
        ..., description="JSON serialized agent state for the thread"
    )


class ThreadUpdateRequest(BaseModel):
    """Request body for PATCH /threads/{thread_id}."""

    name: str | None = Field(None, description="Thread display name")
    is_public: bool | None = Field(
        None,
        description="Whether thread is publicly accessible",
    )
