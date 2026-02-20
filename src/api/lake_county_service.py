"""
Lake County ArcGIS project search.
"""
import asyncio
import time
from typing import Any

import httpx

from src.api.lake_county_config import (
    CIRS_POINT_URL,
    GEOMETRY_TYPE_TO_LAYER,
    LAKE_COUNTY_LAYERS_BY_ID,
    LAKE_COUNTY_SEARCH_LAYER_ID,
    LC_BOUNDARY_URL,
    LC_MUNICIPALITIES_URL,
    PREAPP_GEOMETRY_URL,
    PREAPP_POINT_URL,
    PROJECT_CATEGORY_FLOOD_AUDITS,
    PROJECT_CATEGORY_PROJECTS,
    PROJECT_CATEGORY_STUDIES,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)
MAX_MATCHES = 10
MAX_LIST_PROJECTS = 50

# Fields we fetch unique values for (for filter resolution)
DOMAIN_FIELDS = ["status", "ProjectStatus", "jurisdiction"]

_domains_cache: dict[str, list[str]] | None = None
_domains_cache_ts: float = 0.0
_DOMAINS_CACHE_TTL = 600  # 10 minutes


async def fetch_lake_county_domains() -> dict[str, list[str]]:
    """
    Fetch unique values for status, ProjectStatus, jurisdiction from Representative Points layer.
    Used so the AI can map user terms (e.g. "submitted", "Under Review") to actual field values.
    Cached for 10 minutes to avoid repeated ArcGIS calls.
    """
    global _domains_cache, _domains_cache_ts
    if _domains_cache is not None and (time.monotonic() - _domains_cache_ts) < _DOMAINS_CACHE_TTL:
        return _domains_cache

    layer = LAKE_COUNTY_LAYERS_BY_ID.get(LAKE_COUNTY_SEARCH_LAYER_ID)
    if not layer:
        return {}
    query_url = f"{layer['arcgis_url']}/query"
    result: dict[str, list[str]] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        async def _fetch_domain(field: str) -> tuple[str, list[str]]:
            params = {
                "where": "1=1",
                "outFields": field,
                "returnGeometry": "false",
                "returnDistinctValues": "true",
                "returnExceededLimitFeatures": "true",
                "f": "json",
            }
            try:
                resp = await client.get(query_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning("LC_DOMAINS_FETCH_FAILED", field=field, error=str(e))
                return (field, [])
            if "error" in data:
                return (field, [])
            features = data.get("features", [])
            values = []
            for f in features:
                attr = f.get("attributes", {})
                v = attr.get(field)
                if v is not None and str(v).strip():
                    values.append(str(v).strip())
            return (field, sorted(set(values)))

        domain_results = await asyncio.gather(*[_fetch_domain(f) for f in DOMAIN_FIELDS])
        for field, values in domain_results:
            result[field] = values

    _domains_cache = result
    _domains_cache_ts = time.monotonic()
    return result


MAX_PROJECTS_SEMANTIC_SEARCH = 200
# INFLOW has ~536 Projects, ~69 Studies, ~274 Flood Audits
MAX_PROJECTS_BY_CATEGORY = 1000


def _project_category_where(category: str | None) -> str | None:
    """
    Build WHERE clause for INFLOW project category (Projects, Studies, Flood Audits).
    INFLOW uses ONLY projectsubtype: Study, Flood Audit, and everything else = Projects.
    """
    if not category:
        return None
    c = str(category).strip().lower()
    if c == PROJECT_CATEGORY_PROJECTS:
        return (
            "(projectsubtype IS NULL OR projectsubtype <> 'Flood Audit') "
            "AND (is_study IS NULL OR is_study = 0)"
        )
    if c == PROJECT_CATEGORY_STUDIES:
        return "is_study = 1"
    if c == PROJECT_CATEGORY_FLOOD_AUDITS:
        return "projectsubtype = 'Flood Audit'"
    return None


async def query_lake_county_projects(
    *,
    status: str | None = None,
    project_status: str | None = None,
    project_types: list[str] | None = None,
    jurisdiction: str | None = None,
    project_partners: str | None = None,
    subshed: str | None = None,
    project_category: str | None = None,
    limit: int = MAX_LIST_PROJECTS,
    allow_no_filters: bool = False,
) -> dict[str, Any]:
    """
    Query Lake County projects by filters. Returns matches with PIN + geometry.
    Uses CONTAINS/LIKE for jurisdiction, ProjectPartners, Subshed; exact match for status/ProjectStatus.
    project_types: filter by projecttype IN (...)
    project_category: INFLOW tab - "projects" (exclude Flood Audit + Study), "studies", "flood_audits".
    allow_no_filters: if True, fetch up to MAX_PROJECTS_SEMANTIC_SEARCH when no filters (for semantic search).
    """
    layer = LAKE_COUNTY_LAYERS_BY_ID.get(LAKE_COUNTY_SEARCH_LAYER_ID)
    if not layer:
        return {"found": False, "matches": [], "limit_exceeded": False}

    conditions = []

    cat_where = _project_category_where(project_category)
    if cat_where:
        conditions.append(f"({cat_where})")

    if project_types and len(project_types) > 0:
        safe_types = [str(t).strip().replace("'", "''") for t in project_types if t and str(t).strip()]
        if safe_types:
            in_clause = ",".join(f"'{t}'" for t in safe_types)
            conditions.append(f"projecttype IN ({in_clause})")
    if status and str(status).strip():
        safe = str(status).strip().replace("'", "''")
        conditions.append(f"UPPER(status) = UPPER('{safe}')")
    if project_status and str(project_status).strip():
        safe = str(project_status).strip().replace("'", "''")
        conditions.append(f"UPPER(ProjectStatus) = UPPER('{safe}')")
    if jurisdiction and str(jurisdiction).strip():
        safe = str(jurisdiction).strip().replace("'", "''")
        conditions.append(f"UPPER(jurisdiction) LIKE UPPER('%{safe}%')")
    if project_partners and str(project_partners).strip():
        safe = str(project_partners).strip().replace("'", "''")
        conditions.append(f"UPPER(ProjectPartners) LIKE UPPER('%{safe}%')")
    if subshed and str(subshed).strip():
        safe = str(subshed).strip().replace("'", "''")
        conditions.append(f"UPPER(Subshed) LIKE UPPER('%{safe}%')")

    if not conditions and not allow_no_filters:
        return {"found": False, "matches": [], "limit_exceeded": False, "message": "No filters provided."}

    where = " AND ".join(conditions) if conditions else "1=1"
    if allow_no_filters and not conditions:
        effective_limit = MAX_PROJECTS_SEMANTIC_SEARCH
    elif project_category and project_category.lower() in (PROJECT_CATEGORY_PROJECTS, PROJECT_CATEGORY_STUDIES, PROJECT_CATEGORY_FLOOD_AUDITS):
        effective_limit = max(limit, MAX_PROJECTS_BY_CATEGORY)
    else:
        effective_limit = limit
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": effective_limit + 1,
    }

    query_url = f"{layer['arcgis_url']}/query"
    logger.info("LC_QUERY_PROJECTS", where=where, limit=effective_limit)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(query_url, params=params)
            resp.raise_for_status()
            geojson = resp.json()
    except Exception as e:
        logger.exception("LC_QUERY_HTTP_ERROR", error=str(e))
        return {"found": False, "matches": [], "limit_exceeded": False}

    features = geojson.get("features", [])
    if "error" in geojson:
        return {"found": False, "matches": [], "limit_exceeded": False}

    limit_exceeded = len(features) > effective_limit
    features = features[:effective_limit]

    # Group project IDs by geometry layer for batch fetch (3 HTTP calls total)
    project_ids_by_layer: dict[str, list[int]] = {}
    for feat in features:
        attrs = feat.get("properties", {})
        project_id = attrs.get("project_id")
        geom_type = attrs.get("Geometry")
        if project_id and geom_type:
            layer_id = GEOMETRY_TYPE_TO_LAYER.get(geom_type)
            if layer_id:
                project_ids_by_layer.setdefault(layer_id, []).append(project_id)

    async with httpx.AsyncClient(timeout=120.0) as client:
        geom_by_pid = await _batch_fetch_geometries(client, project_ids_by_layer)

    matches = []
    for feat in features:
        attrs = feat.get("properties", {})
        rep_point_geojson = {"type": "FeatureCollection", "features": [feat]}
        rep_geom = feat.get("geometry")
        project_id = attrs.get("project_id")
        geometry_geojson = geom_by_pid.get(project_id) if project_id else None
        geometry = None
        if geometry_geojson and geometry_geojson.get("features"):
            geometry = geometry_geojson["features"][0].get("geometry")
        if not geometry:
            geometry = rep_geom
        matches.append({
            "rep_point_geojson": rep_point_geojson,
            "geometry_geojson": geometry_geojson,
            "geojson": geometry_geojson or rep_point_geojson,
            "attributes": attrs,
            "geometry": geometry,
        })

    return {"found": True, "matches": matches, "limit_exceeded": limit_exceeded}


async def fetch_municipality_boundary(jurisdiction_name: str) -> dict | None:
    """
    Fetch municipality boundary GeoJSON from Municipal Boundaries layer by name.
    Uses NAME field with LIKE match (case-insensitive). Returns outline geometry only.
    """
    if not jurisdiction_name or not str(jurisdiction_name).strip():
        return None
    safe = str(jurisdiction_name).strip().replace("'", "''")
    where = f"UPPER(NAME) LIKE UPPER('%{safe}%')"
    query_url = f"{LC_MUNICIPALITIES_URL}/query"
    params = {
        "where": where,
        "outFields": "NAME",
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
        logger.warning("LC_MUNI_BOUNDARY_FETCH_FAILED", jurisdiction=jurisdiction_name, error=str(e))
        return None
    if "error" in data or not data.get("features"):
        return None
    return data


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


async def _batch_fetch_geometries(
    client: httpx.AsyncClient,
    project_ids_by_layer: dict[str, list[int]],
) -> dict[int, dict]:
    """
    Fetch geometries for many projects in batch: one query per geometry layer
    using `project_id IN (...)` instead of one HTTP call per project.
    Returns {project_id: FeatureCollection GeoJSON}.
    """
    result: dict[int, dict] = {}

    async def _fetch_layer(layer_id: str, pids: list[int]) -> None:
        layer = LAKE_COUNTY_LAYERS_BY_ID.get(layer_id)
        if not layer or not pids:
            return
        query_url = f"{layer['arcgis_url']}/query"
        id_list = ",".join(str(p) for p in pids)
        # POST avoids URL length limits that cause 404 on large IN clauses
        form_data = {
            "where": f"project_id IN ({id_list})",
            "outFields": "project_id",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultRecordCount": "2000",
        }
        try:
            resp = await client.post(query_url, data=form_data, timeout=120.0)
            resp.raise_for_status()
            geojson = resp.json()
        except Exception as e:
            logger.warning("LC_BATCH_GEOM_ERROR", layer_id=layer_id, count=len(pids), error=str(e))
            return
        if "error" in geojson:
            logger.warning("LC_BATCH_GEOM_ARCGIS_ERROR", layer_id=layer_id, error=geojson.get("error"))
            return
        for feat in geojson.get("features", []):
            pid = feat.get("properties", {}).get("project_id")
            if pid is None:
                continue
            if pid not in result:
                result[pid] = {"type": "FeatureCollection", "features": []}
            result[pid]["features"].append(feat)

    await asyncio.gather(*[
        _fetch_layer(layer_id, pids)
        for layer_id, pids in project_ids_by_layer.items()
        if pids
    ])
    return result


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
        async def _fetch_search_match(feat):
            attrs = feat.get("properties", {})
            rep_geom = feat.get("geometry")
            rep_point_geojson = {"type": "FeatureCollection", "features": [feat]}
            project_id = attrs.get("project_id")
            geom_type = attrs.get("Geometry")
            geometry_geojson = None
            if project_id and geom_type:
                geometry_geojson = await _fetch_project_geometry(client, project_id, geom_type)
            return {
                "rep_point_geojson": rep_point_geojson,
                "geometry_geojson": geometry_geojson,
                "geojson": geometry_geojson or rep_point_geojson,
                "attributes": attrs,
                "geometry": geometry_geojson["features"][0]["geometry"] if geometry_geojson and geometry_geojson.get("features") else rep_geom,
            }
        matches = list(await asyncio.gather(*[_fetch_search_match(f) for f in features[:MAX_MATCHES]]))

    logger.info("LC_SEARCH_SUCCESS", matches_count=len(matches), first_name=matches[0]["attributes"].get("Name") if matches else None)
    return {"found": True, "matches": matches}


MAX_PREAPPS = 200


async def _fetch_preapp_geometries(client: httpx.AsyncClient, preapp_id: int) -> dict | None:
    """Fetch polygon/line geometries from PreApp layer 99 by preapp_id."""
    query_url = f"{PREAPP_GEOMETRY_URL}/query"
    params = {
        "where": f"preapp_id = {preapp_id}",
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
        logger.warning("LC_PREAPP_GEOM_FETCH_FAILED", preapp_id=preapp_id, error=str(e))
        return None
    features = geojson.get("features", [])
    if "error" in geojson or not features:
        return None
    return {"type": "FeatureCollection", "features": features}


async def query_lake_county_preapps(
    *,
    jurisdiction: str | None = None,
    subshed: str | None = None,
    limit: int = MAX_PREAPPS,
) -> dict[str, Any]:
    """
    Query Lake County pre-applications (PreApps).
    Always filters status <> 'Archived'.
    jurisdiction: optional LIKE filter (municipality, e.g. "North Chicago").
    subshed: optional LIKE filter (sub-watershed, e.g. "Lake Michigan", "North Branch Chicago River").
    Returns matches with geometry from layer 98 (points) or 99 (polygons/lines).
    """
    conditions = ["status <> 'Archived'"]
    if jurisdiction and str(jurisdiction).strip():
        safe = str(jurisdiction).strip().replace("'", "''")
        conditions.append(f"UPPER(jurisdiction) LIKE UPPER('%{safe}%')")
    if subshed and str(subshed).strip():
        safe = str(subshed).strip().replace("'", "''")
        conditions.append(f"UPPER(Subshed) LIKE UPPER('%{safe}%')")

    where = " AND ".join(conditions)
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": limit + 1,
    }

    query_url = f"{PREAPP_POINT_URL}/query"
    logger.info("LC_QUERY_PREAPPS", where=where, limit=limit)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(query_url, params=params)
            resp.raise_for_status()
            geojson = resp.json()
    except Exception as e:
        logger.exception("LC_PREAPPS_QUERY_HTTP_ERROR", error=str(e))
        return {"found": False, "matches": [], "limit_exceeded": False}

    features = geojson.get("features", [])
    if "error" in geojson:
        return {"found": False, "matches": [], "limit_exceeded": False}

    limit_exceeded = len(features) > limit
    features = features[:limit]

    # Batch fetch preapp geometries from layer 99 (single query)
    preapp_ids = [
        feat.get("properties", {}).get("preapp_id")
        for feat in features
        if feat.get("properties", {}).get("preapp_id") is not None
    ]
    geom_by_preapp: dict[int, dict] = {}
    if preapp_ids:
        id_list = ",".join(str(p) for p in preapp_ids)
        geom_query_url = f"{PREAPP_GEOMETRY_URL}/query"
        form_data = {
            "where": f"preapp_id IN ({id_list})",
            "outFields": "preapp_id",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultRecordCount": "2000",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as geom_client:
                geom_resp = await geom_client.post(geom_query_url, data=form_data)
                geom_resp.raise_for_status()
                geom_json = geom_resp.json()
            for gfeat in geom_json.get("features", []):
                pid = gfeat.get("properties", {}).get("preapp_id")
                if pid is not None:
                    if pid not in geom_by_preapp:
                        geom_by_preapp[pid] = {"type": "FeatureCollection", "features": []}
                    geom_by_preapp[pid]["features"].append(gfeat)
        except Exception as e:
            logger.warning("LC_BATCH_PREAPP_GEOM_ERROR", count=len(preapp_ids), error=str(e))

    matches = []
    for feat in features:
        attrs = feat.get("properties", {})
        preapp_id = attrs.get("preapp_id")
        point_geom = feat.get("geometry")
        rep_point_geojson = None
        if point_geom and point_geom.get("type") == "Point":
            rep_point_geojson = {"type": "FeatureCollection", "features": [feat]}
        geometry_geojson = geom_by_preapp.get(preapp_id) if preapp_id else None
        geometry = None
        if geometry_geojson and geometry_geojson.get("features"):
            geometry = geometry_geojson["features"][0].get("geometry")
        if not geometry and point_geom:
            geometry = point_geom
        geojson_used = geometry_geojson or rep_point_geojson
        matches.append({
            "rep_point_geojson": rep_point_geojson,
            "geometry_geojson": geometry_geojson,
            "geojson": geojson_used,
            "attributes": attrs,
            "geometry": geometry,
        })

    return {"found": True, "matches": matches, "limit_exceeded": limit_exceeded}


MAX_CONCERNS = 200


async def query_lake_county_concerns(
    *,
    jurisdiction: str | None = None,
    category_report: str | None = None,
    problem: str | None = None,
    frequency_problem: str | None = None,
    limit: int = MAX_CONCERNS,
) -> dict[str, Any]:
    """
    Query Lake County concerns (CIRS).
    Always filters status_CIRS <> 'Archived'.
    jurisdiction, category_report, problem, frequency_problem: optional LIKE filters.
    Point geometry only.
    """
    conditions = ["status_CIRS <> 'Archived'"]
    if jurisdiction and str(jurisdiction).strip():
        safe = str(jurisdiction).strip().replace("'", "''")
        conditions.append(f"UPPER(jurisdiction) LIKE UPPER('%{safe}%')")
    if category_report and str(category_report).strip():
        safe = str(category_report).strip().replace("'", "''")
        conditions.append(f"UPPER(category_report) LIKE UPPER('%{safe}%')")
    if problem and str(problem).strip():
        safe = str(problem).strip().replace("'", "''")
        conditions.append(f"UPPER(problem) LIKE UPPER('%{safe}%')")
    if frequency_problem and str(frequency_problem).strip():
        safe = str(frequency_problem).strip().replace("'", "''")
        conditions.append(f"UPPER(frequency_problem) LIKE UPPER('%{safe}%')")

    where = " AND ".join(conditions)
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": limit + 1,
    }

    query_url = f"{CIRS_POINT_URL}/query"
    logger.info("LC_QUERY_CONCERNS", where=where, limit=limit)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(query_url, params=params)
            resp.raise_for_status()
            geojson = resp.json()
    except Exception as e:
        logger.exception("LC_CONCERNS_QUERY_HTTP_ERROR", error=str(e))
        return {"found": False, "matches": [], "limit_exceeded": False}

    features = geojson.get("features", [])
    if "error" in geojson:
        return {"found": False, "matches": [], "limit_exceeded": False}

    limit_exceeded = len(features) > limit
    features = features[:limit]

    matches = []
    for feat in features:
        attrs = feat.get("properties", {})
        geom = feat.get("geometry")
        rep_point_geojson = {"type": "FeatureCollection", "features": [feat]}
        matches.append({
            "rep_point_geojson": rep_point_geojson,
            "geometry_geojson": None,
            "geojson": rep_point_geojson,
            "attributes": attrs,
            "geometry": geom,
        })

    return {"found": True, "matches": matches, "limit_exceeded": limit_exceeded}
