import asyncio
import json
import re
import time
from typing import Any

from src.api.lake_county_config import (
    CIRS_POINT_URL,
    GEOMETRY_TYPE_TO_LAYER,
    LAKE_COUNTY_LAYERS_BY_ID,
    LAKE_COUNTY_SEARCH_LAYER_ID,
    LC_BOUNDARY_URL,
    LC_COUNTY_BOARD_DISTRICTS_URL,
    LC_DRAINAGE_DISTRICTS_URL,
    LC_MUNICIPALITIES_URL,
    LC_STATE_REP_DISTRICTS_URL,
    LC_STATE_SENATE_DISTRICTS_URL,
    LC_US_CONGRESSIONAL_DISTRICTS_URL,
    PREAPP_GEOMETRY_URL,
    PREAPP_POINT_URL,
    PROJECT_CATEGORY_FLOOD_AUDITS,
    PROJECT_CATEGORY_PROJECTS,
    PROJECT_CATEGORY_STUDIES,
)
from src.api.lake_county_constants import (
    ARCGIS_RESULT_RECORD_COUNT_BATCH,
    ARCGIS_SRID,
    DOMAIN_FIELDS,
    DOMAINS_CACHE_TTL,
    HTTP_TIMEOUT_DOMAINS,
    HTTP_TIMEOUT_MUNICIPALITY,
    HTTP_TIMEOUT_QUERY,
    MAX_CONCERNS,
    MAX_LIST_PROJECTS,
    MAX_MATCHES,
    MAX_PREAPPS,
    MAX_PROJECTS_BY_CATEGORY,
    MAX_PROJECTS_SEMANTIC_SEARCH,
)
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

_domains_cache: dict[str, list[str]] | None = None
_domains_cache_ts: float = 0.0


def _arcgis_client(timeout: float = 30.0) -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=timeout)


async def fetch_lake_county_domains() -> dict[str, list[str]]:
    global _domains_cache, _domains_cache_ts
    if _domains_cache is not None and (time.monotonic() - _domains_cache_ts) < DOMAINS_CACHE_TTL:
        return _domains_cache

    layer = LAKE_COUNTY_LAYERS_BY_ID.get(LAKE_COUNTY_SEARCH_LAYER_ID)
    if not layer:
        return {}
    query_url = f"{layer['arcgis_url']}/query"
    result: dict[str, list[str]] = {}
    client = _arcgis_client(HTTP_TIMEOUT_DOMAINS)

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
            data = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
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


def _project_category_where(category: str | None) -> str | None:
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
    county_board_district_geometry: dict | None = None,
    limit: int = MAX_LIST_PROJECTS,
    allow_no_filters: bool = False,
) -> dict[str, Any]:
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

    if not conditions and not allow_no_filters and not county_board_district_geometry:
        return {"found": False, "matches": [], "limit_exceeded": False, "message": "No filters provided."}

    where = " AND ".join(conditions) if conditions else "1=1"
    if allow_no_filters and not conditions and not county_board_district_geometry:
        effective_limit = MAX_PROJECTS_SEMANTIC_SEARCH
    elif project_category and project_category.lower() in (PROJECT_CATEGORY_PROJECTS, PROJECT_CATEGORY_STUDIES, PROJECT_CATEGORY_FLOOD_AUDITS):
        effective_limit = max(limit, MAX_PROJECTS_BY_CATEGORY)
    else:
        effective_limit = limit

    query_url = f"{layer['arcgis_url']}/query"
    logger.info(
        "LC_QUERY_PROJECTS",
        where=where,
        limit=effective_limit,
        spatial_filter=bool(county_board_district_geometry),
    )

    try:
        client = _arcgis_client(HTTP_TIMEOUT_QUERY)
        if county_board_district_geometry:
            esri_geom = district_geometry_to_esri(county_board_district_geometry)
            if not esri_geom:
                logger.warning("LC_QUERY_SPATIAL_SKIPPED", reason="district_geometry_to_esri returned None")
                return {"found": False, "matches": [], "limit_exceeded": False}
            form_data = {
                "where": where,
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": str(ARCGIS_SRID),
                "f": "geojson",
                "resultRecordCount": str(effective_limit + 1),
                "geometry": json.dumps(esri_geom),
                "geometryType": "esriGeometryPolygon",
                "spatialRel": "esriSpatialRelIntersects",
            }
            geojson = await client.post(query_url, form_data, HTTP_TIMEOUT_QUERY)
        else:
            params = {
                "where": where,
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": ARCGIS_SRID,
                "f": "geojson",
                "resultRecordCount": effective_limit + 1,
            }
            geojson = await client.get(query_url, params, HTTP_TIMEOUT_QUERY)
    except Exception as e:
        logger.exception("LC_QUERY_HTTP_ERROR", error=str(e))
        return {"found": False, "matches": [], "limit_exceeded": False}

    features = geojson.get("features", [])
    if "error" in geojson:
        return {"found": False, "matches": [], "limit_exceeded": False}

    limit_exceeded = len(features) > effective_limit
    features = features[:effective_limit]

    project_ids_by_layer: dict[str, list[int]] = {}
    for feat in features:
        attrs = feat.get("properties", {})
        project_id = attrs.get("project_id")
        geom_type = attrs.get("Geometry")
        if project_id and geom_type:
            layer_id = GEOMETRY_TYPE_TO_LAYER.get(geom_type)
            if layer_id:
                project_ids_by_layer.setdefault(layer_id, []).append(project_id)

    client = _arcgis_client(HTTP_TIMEOUT_QUERY)
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
    if not jurisdiction_name or not str(jurisdiction_name).strip():
        return None
    safe = str(jurisdiction_name).strip().replace("'", "''")
    where = f"UPPER(NAME) LIKE UPPER('%{safe}%')"
    query_url = f"{LC_MUNICIPALITIES_URL}/query"
    params = {
        "where": where,
        "outFields": "NAME",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception as e:
        logger.warning("LC_MUNI_BOUNDARY_FETCH_FAILED", jurisdiction=jurisdiction_name, error=str(e))
        return None
    if "error" in data or not data.get("features"):
        return None
    return data


def district_geometry_to_esri(geom: dict) -> dict | None:
    """Convert district boundary geometry to Esri format for spatial query. Accepts GeoJSON or Esri format."""
    if not geom or not isinstance(geom, dict):
        return None
    # Esri format: "rings" (polygon) or "paths" (same as rings for polygon)
    rings = geom.get("rings") or geom.get("paths")
    if rings and isinstance(rings, list) and len(rings) > 0:
        sr = geom.get("spatialReference") or {"wkid": ARCGIS_SRID}
        return {"rings": rings, "spatialReference": sr}
    # GeoJSON format
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords or not isinstance(coords, (list, tuple)):
        return None
    ring = None
    if gtype == "Polygon":
        if coords and len(coords) > 0:
            ring = coords[0]
    elif gtype == "MultiPolygon":
        if coords and coords[0] and coords[0][0]:
            ring = coords[0][0]
    if not ring or not isinstance(ring, (list, tuple)) or len(ring) < 3:
        return None
    # Esri expects rings; each point [x,y] or [x,y,z] is fine
    return {
        "rings": [ring],
        "spatialReference": {"wkid": ARCGIS_SRID},
    }


async def fetch_county_board_district_boundary(identifier: str) -> dict | None:
    if not identifier or not str(identifier).strip():
        return None
    raw = str(identifier).strip().replace("'", "''")
    if raw.isdigit():
        where = f"CB_DIST = {raw}"
    else:
        where = f"UPPER(NAME) LIKE UPPER('%{raw}%')"
    query_url = f"{LC_COUNTY_BOARD_DISTRICTS_URL}/query"
    params = {
        "where": where,
        "outFields": "NAME,CB_DIST",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception as e:
        logger.warning(
            "LC_CB_DISTRICT_BOUNDARY_FETCH_FAILED",
            identifier=identifier,
            exc_type=type(e).__name__,
            error=str(e),
        )
        return None
    if "error" in data:
        logger.warning(
            "LC_CB_DISTRICT_BOUNDARY_ARCGIS_ERROR",
            identifier=identifier,
            arcgis_error=data.get("error"),
        )
        return None
    if not data.get("features"):
        logger.warning(
            "LC_CB_DISTRICT_BOUNDARY_NO_FEATURES",
            identifier=identifier,
        )
        return None
    return data


def _district_where_clause(
    identifier: str,
    id_field: str,
    name_field: str,
    id_field_is_string: bool = False,
) -> str | None:
    if not identifier or not str(identifier).strip():
        return None
    raw = str(identifier).strip().replace("'", "''")
    if raw.isdigit():
        if id_field_is_string:
            return f"{id_field} = '{raw}'"
        return f"{id_field} = {raw}"
    return f"UPPER({name_field}) LIKE UPPER('%{raw}%')"


async def _fetch_district_boundary_by_where(
    base_url: str, where: str, out_fields: str
) -> dict | None:
    query_url = f"{base_url}/query"
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_MUNICIPALITY)
        return await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception:
        return None


async def _fetch_district_boundary(
    base_url: str,
    identifier: str,
    id_field: str,
    name_field: str,
    out_fields: str,
    log_prefix: str,
    id_field_is_string: bool = False,
) -> dict | None:
    where = _district_where_clause(identifier, id_field, name_field, id_field_is_string)
    if not where:
        return None
    try:
        data = await _fetch_district_boundary_by_where(base_url, where, out_fields)
    except Exception as e:
        logger.warning(
            f"{log_prefix}_FETCH_FAILED",
            identifier=identifier,
            exc_type=type(e).__name__,
            error=str(e),
        )
        return None
    if not data or "error" in data or not data.get("features"):
        return None
    return data


async def _fetch_district_boundary_esri(
    base_url: str, where: str, out_fields: str
) -> dict | None:
    """Fetch same district query with f=json to get geometry in Esri format (rings)."""
    query_url = f"{base_url}/query"
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "json",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception:
        return None
    features = data.get("features") if isinstance(data.get("features"), list) else []
    if "error" in data or not features:
        return None
    geom = features[0].get("geometry") if features else None
    if geom and (geom.get("rings") or geom.get("paths")):
        return geom
    return None


async def _fetch_drainage_all_and_filter_by_name(identifier: str) -> dict | None:
    """Fetch all drainage districts (where=1=1) and filter in Python by identifier. Use when server-side WHERE returns 0."""
    query_url = f"{LC_DRAINAGE_DISTRICTS_URL}/query"
    params = {
        "where": "1=1",
        "outFields": "NAME,CODE",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": 100,
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception:
        return None
    if not isinstance(data, dict) or "error" in data:
        return None
    features = data.get("features") or []
    if not features:
        return None
    # Match identifier words against NAME and CODE (case-insensitive)
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", str(identifier or "")) if w]
    if not words:
        return {"type": "FeatureCollection", "features": [features[0]], "crs": data.get("crs")}
    matched = []
    for f in features:
        props = f.get("properties") or {}
        name = (props.get("NAME") or "").lower()
        code = (props.get("CODE") or "").lower()
        text = f"{name} {code}"
        if all(w in text for w in words):
            matched.append(f)
    if not matched:
        # Fallback: first feature whose NAME or CODE contains the first word
        first_word = words[0]
        for f in features:
            props = f.get("properties") or {}
            if first_word in ((props.get("NAME") or "") + (props.get("CODE") or "")).lower():
                matched.append(f)
                break
    if not matched:
        return None
    return {"type": "FeatureCollection", "features": matched, "crs": data.get("crs")}


async def fetch_drainage_district_boundary(identifier: str) -> dict | None:
    """Drainage districts: identifier by CODE (e.g. 1) or NAME. Returns GeoJSON for map + Esri geometry for spatial query."""
    where_name = _district_where_clause(identifier, "CODE", "NAME", id_field_is_string=True)
    data = None
    where_used = where_name
    if where_name:
        data = await _fetch_district_boundary_by_where(
            LC_DRAINAGE_DISTRICTS_URL, where_name, "NAME,CODE"
        )
    # Fallback: try CODE (string then numeric), then relaxed NAME (e.g. "Union" and "1")
    if not data or not data.get("features"):
        numbers = re.findall(r"\d+", str(identifier or ""))
        if numbers:
            code_val = numbers[0]
            for where_code in (
                f"CODE = '{code_val}'",
                f"CODE = {code_val}",
            ):
                data = await _fetch_district_boundary_by_where(
                    LC_DRAINAGE_DISTRICTS_URL, where_code, "NAME,CODE"
                )
                if data and data.get("features"):
                    where_used = where_code
                    break
    if (not data or not data.get("features")) and identifier:
        # Last resort: relaxed NAME e.g. "Union No 1" -> UPPER(NAME) LIKE '%Union%' AND UPPER(NAME) LIKE '%1%'
        words = re.findall(r"[A-Za-z]+|\d+", str(identifier))
        if len(words) >= 2:
            safe_words = [str(w).replace("'", "''") for w in words[:4]]
            conditions = [f"UPPER(NAME) LIKE UPPER('%{w}%')" for w in safe_words]
            where_relaxed = " AND ".join(conditions)
            data = await _fetch_district_boundary_by_where(
                LC_DRAINAGE_DISTRICTS_URL, where_relaxed, "NAME,CODE"
            )
            if data and data.get("features"):
                where_used = where_relaxed
    # Final fallback: fetch ALL drainage districts (where=1=1), filter in Python by identifier text
    if not data or not data.get("features"):
        data = await _fetch_drainage_all_and_filter_by_name(identifier)
        where_used = "1=1 (client filter)" if data and data.get("features") else where_used
    if not data or not data.get("features"):
        return None
    esri_geom = None
    if "client filter" not in (where_used or ""):
        esri_geom = await _fetch_district_boundary_esri(
            LC_DRAINAGE_DISTRICTS_URL, where_used, "NAME,CODE"
        )
    if not esri_geom and data.get("features"):
        # Use first feature geometry converted to Esri (e.g. from "fetch all" path)
        feat = data["features"][0]
        g = feat.get("geometry")
        if g:
            esri_geom = district_geometry_to_esri(g)
    return {"geojson": data, "esri_geometry": esri_geom}


async def fetch_state_senate_district_boundary(identifier: str) -> dict | None:
    """State Senate districts: identifier by STATE_SEN number or NAME."""
    return await _fetch_district_boundary(
        LC_STATE_SENATE_DISTRICTS_URL,
        identifier,
        "STATE_SEN",
        "NAME",
        "NAME,STATE_SEN,DISTRICT",
        "LC_STATE_SENATE_DISTRICT",
    )


async def fetch_state_representative_district_boundary(identifier: str) -> dict | None:
    """State Representative districts: identifier by STATE_REP number or NAME."""
    return await _fetch_district_boundary(
        LC_STATE_REP_DISTRICTS_URL,
        identifier,
        "STATE_REP",
        "NAME",
        "NAME,STATE_REP,DISTRICT",
        "LC_STATE_REP_DISTRICT",
    )


async def fetch_us_congressional_district_boundary(identifier: str) -> dict | None:
    """U.S. Congressional districts: identifier by US_REP number or NAME."""
    return await _fetch_district_boundary(
        LC_US_CONGRESSIONAL_DISTRICTS_URL,
        identifier,
        "US_REP",
        "NAME",
        "NAME,US_REP,DISTRICT",
        "LC_US_CONG_DISTRICT",
    )


async def fetch_lake_county_boundary() -> dict | None:
    query_url = f"{LC_BOUNDARY_URL}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception as e:
        logger.warning("LC_BOUNDARY_FETCH_FAILED", error=str(e))
        return None
    if "error" in data or not data.get("features"):
        return None
    return data


async def _fetch_project_geometry(
    client: ArcGISClient, project_id: int, geom_type: str
) -> dict | None:
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
        "outSR": ARCGIS_SRID,
        "f": "geojson",
    }
    try:
        geojson = await client.get(query_url, params, HTTP_TIMEOUT_QUERY)
    except Exception as e:
        logger.warning("LC_FETCH_GEOM_ERROR", project_id=project_id, geom_type=geom_type, error=str(e))
        return None
    features = geojson.get("features", [])
    if "error" in geojson or not features:
        return None
    return {"type": "FeatureCollection", "features": features}


async def _batch_fetch_geometries(
    client: ArcGISClient,
    project_ids_by_layer: dict[str, list[int]],
) -> dict[int, dict]:
    result: dict[int, dict] = {}

    async def _fetch_layer(layer_id: str, pids: list[int]) -> None:
        layer = LAKE_COUNTY_LAYERS_BY_ID.get(layer_id)
        if not layer or not pids:
            return
        query_url = f"{layer['arcgis_url']}/query"
        id_list = ",".join(str(p) for p in pids)
        form_data = {
            "where": f"project_id IN ({id_list})",
            "outFields": "project_id",
            "returnGeometry": "true",
            "outSR": str(ARCGIS_SRID),
            "f": "geojson",
            "resultRecordCount": str(ARCGIS_RESULT_RECORD_COUNT_BATCH),
        }
        try:
            geojson = await client.post(query_url, form_data, HTTP_TIMEOUT_QUERY)
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
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": MAX_MATCHES,
    }

    try:
        client = _arcgis_client(HTTP_TIMEOUT_DOMAINS)
        geojson = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
    except Exception as e:
        logger.exception("LC_SEARCH_HTTP_ERROR", error=str(e), error_type=type(e).__name__)
        return {"found": False, "matches": []}

    features = geojson.get("features", [])
    if "error" in geojson:
        logger.error("LC_SEARCH_ARCGIS_ERROR", arcgis_error=geojson.get("error"))
        return {"found": False, "matches": []}

    if not features:
        logger.warning("LC_SEARCH_NO_FEATURES", response_keys=list(geojson.keys()))
        return {"found": False, "matches": []}

    client = _arcgis_client(HTTP_TIMEOUT_DOMAINS)

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


async def query_lake_county_preapps(
    *,
    jurisdiction: str | None = None,
    subshed: str | None = None,
    limit: int = MAX_PREAPPS,
) -> dict[str, Any]:
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
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": limit + 1,
    }
    query_url = f"{PREAPP_POINT_URL}/query"
    logger.info("LC_QUERY_PREAPPS", where=where, limit=limit)

    try:
        client = _arcgis_client(HTTP_TIMEOUT_DOMAINS)
        geojson = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
    except Exception as e:
        logger.exception("LC_PREAPPS_QUERY_HTTP_ERROR", error=str(e))
        return {"found": False, "matches": [], "limit_exceeded": False}

    features = geojson.get("features", [])
    if "error" in geojson:
        return {"found": False, "matches": [], "limit_exceeded": False}

    limit_exceeded = len(features) > limit
    features = features[:limit]

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
            "outSR": str(ARCGIS_SRID),
            "f": "geojson",
            "resultRecordCount": str(ARCGIS_RESULT_RECORD_COUNT_BATCH),
        }
        try:
            client = _arcgis_client(HTTP_TIMEOUT_QUERY)
            geom_json = await client.post(geom_query_url, form_data, HTTP_TIMEOUT_QUERY)
        except Exception as e:
            logger.warning("LC_BATCH_PREAPP_GEOM_ERROR", count=len(preapp_ids), error=str(e))
        else:
            for gfeat in geom_json.get("features", []):
                pid = gfeat.get("properties", {}).get("preapp_id")
                if pid is not None:
                    if pid not in geom_by_preapp:
                        geom_by_preapp[pid] = {"type": "FeatureCollection", "features": []}
                    geom_by_preapp[pid]["features"].append(gfeat)

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


async def query_lake_county_concerns(
    *,
    jurisdiction: str | None = None,
    category_report: str | None = None,
    problem: str | None = None,
    frequency_problem: str | None = None,
    limit: int = MAX_CONCERNS,
) -> dict[str, Any]:
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
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": limit + 1,
    }
    query_url = f"{CIRS_POINT_URL}/query"
    logger.info("LC_QUERY_CONCERNS", where=where, limit=limit)

    try:
        client = _arcgis_client(HTTP_TIMEOUT_DOMAINS)
        geojson = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
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
