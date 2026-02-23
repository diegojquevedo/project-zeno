from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeometryResponse(BaseModel):
    name: str = Field(..., description="Name of the geometry")
    subtype: str = Field(..., description="Subtype of the geometry")
    source: str = Field(..., description="Source of the geometry")
    src_id: int | str = Field(..., description="Source ID of the geometry")
    geometry: dict = Field(..., description="GeoJSON geometry")


class DailyUsageModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    date: datetime
    usage_count: int

    @field_validator("date", mode="before")
    def parse_date(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value
