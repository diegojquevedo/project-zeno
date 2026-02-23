"""
Custom exceptions. Use instead of generic Exception or HTTPException where appropriate.
"""


class ProjectZenoException(Exception):
    """Base exception for the project."""

    pass


class AgentExecutionError(ProjectZenoException):
    """Error during LangGraph agent execution."""

    pass


class ResourceNotFoundError(ProjectZenoException):
    """Resource not found in database."""

    pass


class ConfigurationError(ProjectZenoException):
    """Invalid or missing configuration."""

    pass


class AuthenticationError(ProjectZenoException):
    """Authentication failed."""

    pass


class QuotaExceededError(ProjectZenoException):
    """User or IP quota exceeded."""

    pass
