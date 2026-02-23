from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RatingCreateRequest(BaseModel):
    trace_id: str
    rating: int
    comment: Optional[str] = None

    @field_validator("rating")
    def validate_rating(cls, v):
        if v not in [-1, 1]:
            raise ValueError(
                "Rating must be either 1 (thumbs up) or -1 (thumbs down)"
            )
        return v


class RatingModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    thread_id: str
    trace_id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
