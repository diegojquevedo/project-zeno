"""
HTTP middleware: CORS, request logging, request ID.
"""

import uuid

import structlog
from fastapi import Request, Response, status

from src.core.logging import get_logger

logger = get_logger(__name__)


async def request_logging_middleware(
    request: Request, call_next
) -> Response:
    """Log requests and bind request ID to context."""
    req_id = uuid.uuid4().hex

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=req_id)

    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        request_id=req_id,
    )
    response_code = None
    response = None

    try:
        response = await call_next(request)
        response_code = response.status_code
    except Exception as e:
        logger.exception(
            "Request failed with error",
            method=request.method,
            url=str(request.url),
            error=str(e),
            request_id=req_id,
        )
        response_code = 500
        raise
    finally:
        if response is None:
            response = Response(
                content="Internal Server Error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "Response sent",
            method=request.method,
            url=str(request.url),
            status_code=response_code,
            request_id=req_id,
        )
    return response
