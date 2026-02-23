from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agents.graph import (
    close_checkpointer_pool,
    get_checkpointer_pool,
)
from src.api.v1.router import api_router
from src.core.exceptions import ResourceNotFoundError
from src.core.middleware import request_logging_middleware
from src.core.security import get_cookie_signer
from src.shared.database import (
    close_global_pool,
    initialize_global_pool,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init and cleanup."""
    await initialize_global_pool()
    await get_checkpointer_pool()
    yield
    await close_global_pool()
    await close_checkpointer_pool()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        lifespan=lifespan,
        title="Zeno API",
        description="API for Zeno LangGraph-based agent workflow",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(request_logging_middleware)

    app.include_router(api_router, prefix="/api/v1")

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        _request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.args[0] if exc.args else "Resource not found"},
        )

    # Store signer on app state for endpoints that need it
    app.state.signer = get_cookie_signer()

    return app
