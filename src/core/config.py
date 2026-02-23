from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import src.shared.env  # noqa: F401


class Settings(BaseSettings):
    """Unified settings for the entire application."""

    model_config = SettingsConfigDict(
        env_file=[".env", ".env.local"],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    app_env: str = Field(default="production", alias="STAGE")
    project_name: str = Field(default="project-zeno", alias="PROJECT_NAME")
    debug: bool = Field(default=False, alias="DEBUG")

    # -------------------------------------------------------------------------
    # Database (shared)
    # -------------------------------------------------------------------------
    database_url: str = Field(..., alias="DATABASE_URL")
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=30, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")

    # -------------------------------------------------------------------------
    # External APIs (shared)
    # -------------------------------------------------------------------------
    eoapi_base_url: str = Field(
        default="https://eoapi.staging.globalnaturewatch.org",
        alias="EOAPI_BASE_URL",
    )
    analytics_base_url: str = Field(
        default="https://analytics.globalnaturewatch.org",
        alias="ANALYTICS_BASE_URL",
    )
    smc_api_base: str = Field(
        default="https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services",
        alias="SMC_API_BASE",
    )

    # -------------------------------------------------------------------------
    # Dataset embeddings (shared)
    # -------------------------------------------------------------------------
    dataset_embeddings_db: str = Field(
        default="gnw-dataset-index-gemini-v1",
        alias="DATASET_EMBEDDINGS_DB",
    )
    dataset_embeddings_model: str = Field(
        default="models/gemini-embedding-001",
        alias="DATASET_EMBEDDINGS_MODEL",
    )
    dataset_embeddings_task_type: str = Field(
        default="RETRIEVAL_QUERY",
        alias="DATASET_EMBEDDINGS_TASK_TYPE",
    )

    # -------------------------------------------------------------------------
    # API / Auth
    # -------------------------------------------------------------------------
    cookie_signer_secret_key: str = Field(..., alias="COOKIE_SIGNER_SECRET_KEY")
    nextjs_api_key: str = Field(..., alias="NEXTJS_API_KEY")
    domains_allowlist_str: str = Field(default="", alias="DOMAINS_ALLOWLIST")
    max_user_signups: int = Field(default=-1, alias="MAX_USER_SIGNUPS")
    allow_public_signups: bool = Field(
        default=False, alias="ALLOW_PUBLIC_SIGNUPS"
    )
    allow_anonymous_chat: bool = Field(
        default=False, alias="ALLOW_ANONYMOUS_CHAT"
    )
    arcgis_api_key: Optional[str] = Field(default=None, alias="ARCGIS_API_KEY")
    resource_watch_auth_url: str = Field(
        default="https://api.resourcewatch.org/auth/user/me",
        alias="RESOURCE_WATCH_AUTH_URL",
    )

    # -------------------------------------------------------------------------
    # Quotas
    # -------------------------------------------------------------------------
    daily_quota_warning_threshold: int = 5
    admin_user_daily_quota: int = 100
    regular_user_daily_quota: int = 25
    pro_user_daily_quota: int = 50
    machine_user_daily_quota: int = 99999
    anonymous_user_daily_quota: int = 100
    ip_address_daily_quota: int = 50
    enable_quota_checking: bool = True

    # -------------------------------------------------------------------------
    # Agent / LLM
    # -------------------------------------------------------------------------
    model: str = Field(default="gemini-3-flash-preview", alias="MODEL")
    small_model: str = Field(
        default="gemini-3-flash-preview", alias="SMALL_MODEL"
    )
    coding_model: str = Field(
        default="gemini-3-flash-preview", alias="CODING_MODEL"
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="text", alias="LOG_FORMAT")
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")
    log_file_path: str = Field(default="logs/zeno.log", alias="LOG_FILE_PATH")

    # -------------------------------------------------------------------------
    # Computed / helpers
    # -------------------------------------------------------------------------

    @property
    def domains_allowlist(self) -> list[str]:
        if not self.domains_allowlist_str.strip():
            return []
        return [
            domain.strip()
            for domain in self.domains_allowlist_str.split(",")
        ]

    @field_validator("nextjs_api_key")
    @classmethod
    def validate_nextjs_api_key(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError(
                "NEXTJS_API_KEY must be set to a non-empty string"
            )
        return value

    def get_database_url_for_psycopg(self) -> str:
        """Database URL with postgresql:// (psycopg) instead of postgresql+asyncpg://."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )

    def get_database_url_for_psycopg2(self) -> str:
        """Database URL with postgresql+psycopg2:// (sync driver) for ingest scripts."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )


settings = Settings()
