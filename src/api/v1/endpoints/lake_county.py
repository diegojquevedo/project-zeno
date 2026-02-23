import httpx
from fastapi import APIRouter, HTTPException

from src.api.lake_county_config import (
    LAKE_COUNTY_BOUNDS,
    LAKE_COUNTY_LAYERS,
    LAKE_COUNTY_LAYERS_BY_ID,
)
from src.core.config import settings
from src.services.lake_county_service import (
    fetch_lake_county_boundary,
    fetch_lake_county_domains,
    fetch_municipality_boundary,
    query_lake_county_projects,
    search_lake_county_project,
)
from src.shared.logging_config import get_logger

router = APIRouter(prefix="/lake_county", tags=["lake_county"])
logger = get_logger(__name__)


@router.get("/layers")
async def get_lake_county_layers():
    """List available Lake County layers."""
    return {"layers": LAKE_COUNTY_LAYERS}


@router.get("/boundary")
async def get_lake_county_boundary():
    """Fetch Lake County Boundary GeoJSON for map overlay."""
    boundary = await fetch_lake_county_boundary()
    if boundary and boundary.get("features"):
        return boundary
    [[wx, sy], [ex, ny]] = LAKE_COUNTY_BOUNDS
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[wx, sy], [ex, sy], [ex, ny], [wx, ny], [wx, sy]]
                    ],
                },
                "properties": {},
            }
        ],
    }


@router.get("/municipality")
async def get_lake_county_municipality(name: str = ""):
    """Fetch municipality boundary GeoJSON by name."""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="name parameter required")
    boundary = await fetch_municipality_boundary(name.strip())
    if boundary and boundary.get("features"):
        return boundary
    raise HTTPException(
        status_code=404,
        detail=f"No municipality found matching '{name}'",
    )


@router.get("/domains")
async def get_lake_county_domains():
    """Fetch unique values for status, ProjectStatus, jurisdiction."""
    return await fetch_lake_county_domains()


@router.get("/projects")
async def list_lake_county_projects_endpoint(
    status: str | None = None,
    project_status: str | None = None,
    project_types: str | None = None,
    jurisdiction: str | None = None,
    project_partners: str | None = None,
    project_category: str | None = None,
    limit: int = 50,
):
    """List Lake County projects by filters."""
    if limit > 50:
        limit = 50
    types_list = (
        [t.strip() for t in (project_types or "").split(",") if t.strip()]
        or None
    )
    projects, limit_exceeded = await query_lake_county_projects(
        status=status,
        project_status=project_status,
        project_types=types_list,
        jurisdiction=jurisdiction,
        project_partners=project_partners,
        project_category=project_category,
        limit=limit,
    )
    return {"projects": projects, "limit_exceeded": limit_exceeded}


@router.get("/project/search")
async def search_lake_county_projects_endpoint(q: str = ""):
    """Search Lake County projects by name."""
    if not q or not q.strip():
        return {"matches": []}
    matches = await search_lake_county_project(q.strip())
    return {"matches": matches}


@router.get("/{layer_id}/features")
async def get_lake_county_features(
    layer_id: str,
    minx: float = -88.33,
    miny: float = 41.99,
    maxx: float = -87.67,
    maxy: float = 42.69,
):
    """Fetch features from a Lake County ArcGIS layer by bbox."""
    layer = LAKE_COUNTY_LAYERS_BY_ID.get(layer_id)
    if not layer:
        raise HTTPException(
            status_code=404,
            detail=f"Layer '{layer_id}' not found. Use GET /api/v1/lake_county/layers",
        )

    from src.infrastructure.external.arcgis_client import ArcGISClient

    arcgis_url = layer["arcgis_url"]
    query_url = f"{arcgis_url}/query"
    client = ArcGISClient(
        api_key=settings.arcgis_api_key, timeout=30.0
    )
    try:
        return await client.query_bbox(query_url, minx, miny, maxx, maxy)
    except httpx.HTTPStatusError as e:
        logger.exception(
            "ArcGIS query failed for %s: %s", layer_id, e.response.text
        )
        raise HTTPException(
            status_code=502,
            detail=f"ArcGIS service error: {e.response.text[:200]}",
        )
