from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., description="The query")
    user_persona: Optional[str] = Field(None, description="The user persona")
    ui_context: Optional[dict] = None
    ui_action_only: Optional[bool] = False
    thread_id: Optional[str] = Field(None, description="The thread ID")
    metadata: Optional[dict] = Field(None, description="The metadata")
    session_id: Optional[str] = Field(None, description="The session ID")
    user_id: Optional[str] = Field(None, description="The user ID")
    tags: Optional[list] = Field(None, description="The tags")
