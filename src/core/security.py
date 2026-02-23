"""
Security utilities: cookie signing, hashing, JWT (if needed).
"""

from itsdangerous import TimestampSigner

from src.core.config import settings


def get_cookie_signer() -> TimestampSigner:
    """Return configured TimestampSigner for anonymous session cookies."""
    return TimestampSigner(settings.cookie_signer_secret_key)
