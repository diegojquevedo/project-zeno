from datetime import datetime
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    alias_generators,
    field_validator,
)

from src.api.user_profile_configs.countries import COUNTRIES
from src.api.user_profile_configs.gis_expertise import GIS_EXPERTISE_LEVELS
from src.api.user_profile_configs.languages import LANGUAGES
from src.api.user_profile_configs.sectors import SECTOR_ROLES, SECTORS
from src.api.user_profile_configs.topics import TOPICS
from src.models import UserType


class UserModel(BaseModel):
    """User model with relationships to threads and custom areas."""

    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel,
        from_attributes=True,
        populate_by_name=True,
    )
    id: str
    name: str
    email: str
    created_at: datetime
    updated_at: datetime
    threads: list = []
    user_type: UserType = UserType.REGULAR
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_description: Optional[str] = Field(
        None, description="What are you looking for or trying to do with Zeno?"
    )
    sector_code: Optional[str] = None
    role_code: Optional[str] = None
    job_title: Optional[str] = None
    company_organization: Optional[str] = None
    country_code: Optional[str] = None
    preferred_language_code: Optional[str] = None
    gis_expertise_level: Optional[str] = None
    areas_of_interest: Optional[str] = None
    topics: Optional[List[str]] = None
    receive_news_emails: bool = False
    help_test_features: bool = False
    has_profile: bool = False

    @field_validator("created_at", "updated_at", mode="before")
    def parse_dates(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).replace(tzinfo=None)
            except ValueError:
                return value
        return value

    @field_validator("sector_code")
    def validate_sector_code(cls, v):
        if v is not None and v not in SECTORS:
            raise ValueError(f"Invalid sector code: {v}")
        return v

    @field_validator("role_code")
    def validate_role_code(cls, v, info):
        if v is not None:
            sector_code = info.data.get("sector_code")
            if sector_code and sector_code in SECTOR_ROLES:
                if v not in SECTOR_ROLES[sector_code]:
                    raise ValueError(
                        f"Invalid role code: {v} for sector: {sector_code}"
                    )
            elif v != "other":
                raise ValueError(f"Invalid role code: {v}")
        return v

    @field_validator("country_code")
    def validate_country_code(cls, v):
        if v is not None and v not in COUNTRIES:
            raise ValueError(f"Invalid country code: {v}")
        return v

    @field_validator("preferred_language_code")
    def validate_language_code(cls, v):
        if v is not None and v not in LANGUAGES:
            raise ValueError(f"Invalid language code: {v}")
        return v

    @field_validator("gis_expertise_level")
    def validate_gis_expertise(cls, v):
        if v is not None and v not in GIS_EXPERTISE_LEVELS:
            raise ValueError(f"Invalid GIS expertise level: {v}")
        return v

    @field_validator("topics")
    def validate_topics(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("Topics must be a list")
            for topic in v:
                if topic not in TOPICS:
                    raise ValueError(f"Invalid topic: {topic}")
        return v


class UserProfileUpdateRequest(BaseModel):
    """Request schema for updating user profile fields."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_description: Optional[str] = Field(
        None, description="What are you looking for or trying to do with Zeno?"
    )
    sector_code: Optional[str] = None
    role_code: Optional[str] = None
    job_title: Optional[str] = None
    company_organization: Optional[str] = None
    country_code: Optional[str] = None
    preferred_language_code: Optional[str] = None
    gis_expertise_level: Optional[str] = None
    areas_of_interest: Optional[str] = None
    topics: Optional[List[str]] = None
    receive_news_emails: Optional[bool] = None
    help_test_features: Optional[bool] = None
    has_profile: Optional[bool] = None

    @field_validator("sector_code")
    def validate_sector_code(cls, v):
        if v is not None and v not in SECTORS:
            raise ValueError(f"Invalid sector code: {v}")
        return v

    @field_validator("role_code")
    def validate_role_code(cls, v, info):
        if v is not None:
            sector_code = info.data.get("sector_code")
            if sector_code and sector_code in SECTOR_ROLES:
                if v not in SECTOR_ROLES[sector_code]:
                    raise ValueError(
                        f"Invalid role code: {v} for sector: {sector_code}"
                    )
            elif v != "other":
                raise ValueError(f"Invalid role code: {v}")
        return v

    @field_validator("country_code")
    def validate_country_code(cls, v):
        if v is not None and v not in COUNTRIES:
            raise ValueError(f"Invalid country code: {v}")
        return v

    @field_validator("preferred_language_code")
    def validate_language_code(cls, v):
        if v is not None and v not in LANGUAGES:
            raise ValueError(f"Invalid language code: {v}")
        return v

    @field_validator("gis_expertise_level")
    def validate_gis_expertise(cls, v):
        if v is not None and v not in GIS_EXPERTISE_LEVELS:
            raise ValueError(f"Invalid GIS expertise level: {v}")
        return v

    @field_validator("topics")
    def validate_topics(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("Topics must be a list")
            for topic in v:
                if topic not in TOPICS:
                    raise ValueError(f"Invalid topic: {topic}")
        return v


class ProfileConfigResponse(BaseModel):
    """Response schema for profile configuration options."""

    sectors: dict[str, str] = SECTORS
    sector_roles: dict[str, dict[str, str]] = SECTOR_ROLES
    countries: dict[str, str] = COUNTRIES
    languages: dict[str, str] = LANGUAGES
    gis_expertise_levels: dict[str, str] = GIS_EXPERTISE_LEVELS
    topics: dict[str, str] = TOPICS


class QuotaModel(BaseModel):
    """Quota information."""

    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel,
        from_attributes=True,
        populate_by_name=True,
    )
    prompts_used: Optional[int] = Field(
        None, description="Number of prompts used today"
    )
    prompt_quota: Optional[int] = Field(
        None, description="Prompt quota for the user"
    )


class UserWithQuotaModel(UserModel, QuotaModel):
    """User model with quota information."""

    pass
