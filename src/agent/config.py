from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class _AgentSettings(BaseSettings):
    """Agent-specific settings for model configuration."""

    # Model configuration - all use flash for speed
    model: str = Field(default="gemini-3-flash-preview", alias="MODEL")
    small_model: str = Field(default="gemini-3-flash-preview", alias="SMALL_MODEL")
    coding_model: str = Field(default="gemini-3-flash-preview", alias="CODING_MODEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Create a singleton instance
AgentSettings = _AgentSettings()
