from datetime import datetime
from typing import List
from uuid import UUID

from geojson_pydantic import Polygon
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomAreaNameRequest(BaseModel):
    type: str = Field(
        "FeatureCollection", description="Type must be FeatureCollection"
    )
    features: list = Field(
        ..., description="Array of GeoJSON Feature objects"
    )


class CustomAreaNameResponse(BaseModel):
    name: str = Field(
        ...,
        description="Generated geographic name for the area",
        max_length=100,
    )

    @field_validator("name", mode="before")
    def truncate_area_name(cls, value):
        if isinstance(value, str) and len(value) > 100:
            return value[:100]
        return value


class CustomAreaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: str
    name: str
    geometries: List
    created_at: datetime
    updated_at: datetime


class CustomAreaCreate(BaseModel):
    name: str
    geometries: List[Polygon]
