from fastapi import APIRouter

from src.api.v1.endpoints import (
    auth,
    chat,
    custom_areas,
    geometry,
    health,
    lake_county,
    metadata,
    profile,
    quota,
    threads,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(quota.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(threads.router)
api_router.include_router(profile.router)
api_router.include_router(metadata.router)
api_router.include_router(custom_areas.router)
api_router.include_router(geometry.router)
api_router.include_router(lake_county.router)
