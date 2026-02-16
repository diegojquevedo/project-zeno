"""
Lake County ArcGIS project search.
"""
from typing import Any

import httpx

from src.api.lake_county_config import (
    GEOMETRY_TYPE_TO_LAYER,
    LAKE_COUNTY_LAYERS_BY_ID,
    LAKE_COUNTY_SEARCH_LAYER_ID,
    LC_BOUNDARY_URL,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)
MAX_MATCHES = 10


async def fetch_lake_county_boundary() -> dict | None:
    """Fetch Lake County Boundary GeoJSON from ArcGIS MapServer."""
    query_url = f"{LC_BOUNDARY_URL}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(query_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("LC_BOUNDARY_FETCH_FAILED", error=str(e))
        return None
    if "error" in data or not data.get("features"):
        return None
    return data


async def _fetch_project_geometry(client: httpx.AsyncClient, project_id: int, geom_type: str) -> dict | None:
    """Fetch geometry from Areas/Lines/Points layer by project_id."""
    layer_id = GEOMETRY_TYPE_TO_LAYER.get(geom_type) if geom_type else None
    if not layer_id:
        return None
    layer = LAKE_COUNTY_LAYERS_BY_ID.get(layer_id)
    if not layer:
        return None
    query_url = f"{layer['arcgis_url']}/query"
    params = {
        "where": f"project_id = {project_id}",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
    }
    try:
        resp = await client.get(query_url, params=params)
        resp.raise_for_status()
        geojson = resp.json()
    except Exception as e:
        logger.warning("LC_FETCH_GEOM_ERROR", project_id=project_id, geom_type=geom_type, error=str(e))
        return None
    features = geojson.get("features", [])
    if "error" in geojson or not features:
        return None
    return {"type": "FeatureCollection", "features": features}


async def search_lake_county_project(name: str) -> dict[str, Any]:
    """
    Search for Lake County projects by name (partial match, CONTAINS).
    Returns all matches (up to MAX_MATCHES) with geometry and attributes.
    """
    logger.info("LC_SEARCH_START", name=name, layer_id=LAKE_COUNTY_SEARCH_LAYER_ID)

    if not name or not name.strip():
        logger.warning("LC_SEARCH_EMPTY_NAME")
        return {"found": False, "matches": []}

    layer = LAKE_COUNTY_LAYERS_BY_ID.get(LAKE_COUNTY_SEARCH_LAYER_ID)
    if not layer:
        logger.error("LC_SEARCH_NO_LAYER", search_layer_id=LAKE_COUNTY_SEARCH_LAYER_ID)
        return {"found": False, "matches": []}

    query_url = f"{layer['arcgis_url']}/query"
    safe_name = name.strip().replace("'", "''")
    where = f"UPPER(Name) LIKE UPPER('%{safe_name}%')"

    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": MAX_MATCHES,
    }
    # Lake County SMC service is public - token causes 498 Invalid token if expired
    # arcgis_key = os.environ.get("ARCGIS_API_KEY")
    # if arcgis_key:
    #     params["token"] = arcgis_key
    has_token = False

    logger.info(
        "LC_SEARCH_REQUEST",
        query_url=query_url,
        where=where,
        has_token=has_token,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(query_url, params=params)
            logger.info(
                "LC_SEARCH_HTTP_RESPONSE",
                status=resp.status_code,
                url=str(resp.url),
            )

            resp.raise_for_status()
            geojson = resp.json()
    except Exception as e:
        logger.exception("LC_SEARCH_HTTP_ERROR", error=str(e), error_type=type(e).__name__)
        return {"found": False, "matches": []}

    features = geojson.get("features", [])
    if "error" in geojson:
        logger.error("LC_SEARCH_ARCGIS_ERROR", arcgis_error=geojson.get("error"))
        return {"found": False, "matches": []}

    logger.info("LC_SEARCH_FEATURES_COUNT", count=len(features), total=geojson.get("properties", {}).get("exceededTransferLimit"))

    if not features:
        logger.warning("LC_SEARCH_NO_FEATURES", response_keys=list(geojson.keys()))
        return {"found": False, "matches": []}

    matches = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for feat in features[:MAX_MATCHES]:
            attrs = feat.get("properties", {})
            rep_geom = feat.get("geometry")
            rep_point_geojson = {"type": "FeatureCollection", "features": [feat]}
            project_id = attrs.get("project_id")
            geom_type = attrs.get("Geometry")
            geometry_geojson = None
            if project_id and geom_type:
                geometry_geojson = await _fetch_project_geometry(client, project_id, geom_type)
            matches.append({
                "rep_point_geojson": rep_point_geojson,
                "geometry_geojson": geometry_geojson,
                "geojson": geometry_geojson or rep_point_geojson,
                "attributes": attrs,
                "geometry": geometry_geojson["features"][0]["geometry"] if geometry_geojson and geometry_geojson.get("features") else rep_geom,
            })

    logger.info("LC_SEARCH_SUCCESS", matches_count=len(matches), first_name=matches[0]["attributes"].get("Name") if matches else None)
    return {"found": True, "matches": matches}
