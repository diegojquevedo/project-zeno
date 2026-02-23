from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check for load balancers and orchestrators."""
    return {"status": "ok"}
