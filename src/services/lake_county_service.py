import asyncio
import json
import re
import time
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

from src.api.lake_county_config import (
    CIRS_POINT_URL,
    GEOMETRY_TYPE_TO_LAYER,
    LAKE_COUNTY_LAYERS_BY_ID,
    LAKE_COUNTY_SEARCH_LAYER_ID,
    LC_BOUNDARY_URL,
    LC_COUNTY_BOARD_DISTRICTS_URL,
    LC_DRAINAGE_DISTRICTS_URL,
    LC_MUNICIPALITIES_URL,
    LC_NFHL_FLOOD_ZONES_URL,
    LC_SOILS_URL,
    LC_STATE_REP_DISTRICTS_URL,
    LC_STATE_SENATE_DISTRICTS_URL,
    LC_SUBWATERSHEDS_URL,
    LC_US_CONGRESSIONAL_DISTRICTS_URL,
    LC_WATERSHEDS_URL,
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
    HTTP_TIMEOUT_WABDRAINAGE,
    HTTP_TIMEOUT_WATERSHED,
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

    try:
        client = _arcgis_client(HTTP_TIMEOUT_QUERY)
        if county_board_district_geometry:
            esri_geom = district_geometry_to_esri(county_board_district_geometry)
            if not esri_geom:
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


async def get_place_center(place_name: str) -> tuple[float, float] | None:
    """
    Resolve a place name (e.g. Gurnee) to (longitude, latitude) using Lake County
    municipality boundaries. Returns the centroid of the matching municipality.
    """
    if not place_name or not str(place_name).strip():
        return None
    boundary = await fetch_municipality_boundary(place_name.strip())
    if not boundary or not boundary.get("features"):
        return None
    feat = boundary["features"][0]
    geom_dict = feat.get("geometry") or feat.get("geom")
    if not geom_dict:
        return None
    try:
        geom = shape(geom_dict)
        cent = geom.centroid
        return (float(cent.x), float(cent.y))
    except Exception as e:
        logger.warning("LC_PLACE_CENTER_FAILED", place=place_name, error=str(e))
        return None


def buffer_geometry_meters(geom: dict, radius_m: float) -> dict | None:
    if not geom or not isinstance(geom, dict) or radius_m <= 0 or radius_m > 5000:
        return None
    try:
        shp = shape(geom)
        if shp.is_empty:
            return None
        cent = shp.centroid
        lat, lon = float(cent.y), float(cent.x)
        aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m"
        transformer_to = Transformer.from_proj("EPSG:4326", aeqd, always_xy=True)
        transformer_from = Transformer.from_proj(aeqd, "EPSG:4326", always_xy=True)
        shp_aeqd = shapely_transform(transformer_to.transform, shp)
        buffered = shp_aeqd.buffer(radius_m)
        wgs84 = shapely_transform(transformer_from.transform, buffered)
        result = mapping(wgs84)
        if result.get("type") in ("Polygon", "MultiPolygon") and result.get("coordinates"):
            return result
        return None
    except Exception:
        return None


def buffer_point_km(lon: float, lat: float, radius_km: float) -> dict | None:
    """
    Create a circular polygon (buffer) of radius_km around (lon, lat) in WGS84.
    Returns GeoJSON Polygon suitable for spatial query and map display.
    """
    if radius_km <= 0 or radius_km > 200:
        return None
    radius_m = radius_km * 1000.0
    try:
        aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m"
        transformer = Transformer.from_proj(aeqd, "EPSG:4326", always_xy=True)
        circle = Point(0, 0).buffer(radius_m)
        wgs84 = shapely_transform(transformer.transform, circle)
        # GeoJSON: Polygon coordinates = [exterior ring]; ring = list of [x,y] (lon, lat)
        ext = wgs84.exterior
        ring = [[float(x), float(y)] for x, y in ext.coords]
        if not ring or len(ring) < 3:
            return None
        return {"type": "Polygon", "coordinates": [ring]}
    except Exception as e:
        logger.warning("LC_BUFFER_FAILED", lon=lon, lat=lat, radius_km=radius_km, error=str(e))
        return None


def _is_web_mercator_coords(ring: list) -> bool:
    if not ring or len(ring) < 2:
        return False
    x, y = ring[0][0], ring[0][1]
    return abs(x) > 180 or abs(y) > 90


def _reproject_ring_3857_to_4326(ring: list) -> list:
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    return [[float(transformer.transform(x, y)[0]), float(transformer.transform(x, y)[1])] for x, y in ring]


def _reproject_geojson_3857_to_4326(geom: dict) -> dict | None:
    if not geom or not isinstance(geom, dict):
        return geom
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return geom
    try:
        if gtype == "Polygon" and coords and coords[0]:
            if not _is_web_mercator_coords(coords[0]):
                return geom
            new_coords = [_reproject_ring_3857_to_4326(ring) for ring in coords]
            return {"type": "Polygon", "coordinates": new_coords}
        if gtype == "MultiPolygon" and coords:
            first_ring = coords[0][0] if coords[0] else []
            if not first_ring or not _is_web_mercator_coords(first_ring):
                return geom
            new_coords = [[_reproject_ring_3857_to_4326(ring) for ring in poly] for poly in coords]
            return {"type": "MultiPolygon", "coordinates": new_coords}
    except Exception:
        pass
    return geom


def _ensure_feature_collection_wgs84(data: dict | None) -> dict | None:
    if not data or not data.get("features"):
        return data
    out = {"type": data.get("type", "FeatureCollection"), "features": [], "crs": data.get("crs")}
    for feat in data["features"]:
        g = feat.get("geometry")
        if g and isinstance(g, dict):
            g = _reproject_geojson_3857_to_4326(g)
        out["features"].append({**feat, "geometry": g} if g else feat)
    return out


def _geojson_to_esri_rings(geom: dict) -> list | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords or not isinstance(coords, (list, tuple)):
        return None
    rings: list = []
    if gtype == "Polygon":
        for part in coords:
            if part and len(part) >= 3:
                rings.append(part)
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly and poly[0] and len(poly[0]) >= 3:
                for part in poly:
                    if part and len(part) >= 3:
                        rings.append(part)
    if not rings:
        return None
    return rings


def district_geometry_to_esri(geom: dict) -> dict | None:
    if not geom or not isinstance(geom, dict):
        return None
    rings = geom.get("rings") or geom.get("paths")
    if rings and isinstance(rings, list) and len(rings) > 0:
        sr = geom.get("spatialReference") or {"wkid": ARCGIS_SRID}
        return {"rings": rings, "spatialReference": sr}
    rings = _geojson_to_esri_rings(geom)
    if not rings:
        return None
    return {"rings": rings, "spatialReference": {"wkid": ARCGIS_SRID}}


def _geojson_to_esri_for_spatial_query(
    geom: dict,
) -> tuple[dict, str] | None:
    """Convert GeoJSON geometry to Esri JSON for spatial query. Returns (esri_geom, geometry_type) or None."""
    if not geom or not isinstance(geom, dict):
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if coords is None:
        return None
    sr = {"wkid": ARCGIS_SRID}
    if gtype == "Point":
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            return None
        lon, lat = float(coords[0]), float(coords[1])
        return ({"x": lon, "y": lat, "spatialReference": sr}, "esriGeometryPoint")
    if gtype == "LineString":
        if not coords or len(coords) < 2:
            return None
        paths = [[[float(c[0]), float(c[1])] for c in coords]]
        return ({"paths": paths, "spatialReference": sr}, "esriGeometryPolyline")
    if gtype in ("Polygon", "MultiPolygon"):
        rings = _geojson_to_esri_rings(geom)
        if not rings:
            return None
        return ({"rings": rings, "spatialReference": sr}, "esriGeometryPolygon")
    return None


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
    base_url: str, where: str, out_fields: str, timeout: float | None = None
) -> dict | None:
    timeout = timeout if timeout is not None else HTTP_TIMEOUT_MUNICIPALITY
    query_url = f"{base_url}/query"
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
    }
    try:
        client = _arcgis_client(timeout)
        data = await client.get(query_url, params, timeout)
        if data and "error" in data:
            return None
        return data
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
    timeout: float | None = None,
) -> dict | None:
    where = _district_where_clause(identifier, id_field, name_field, id_field_is_string)
    if not where:
        return None
    try:
        data = await _fetch_district_boundary_by_where(base_url, where, out_fields, timeout=timeout)
    except Exception:
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


def _drainage_token_matches_identifier_word(word: str, name_code_text: str) -> bool:
    w = (word or "").lower()
    h = (name_code_text or "").lower()
    if not w:
        return True
    if w in h:
        return True
    if w == "no" and "number" in h:
        return True
    if w == "number" and "no" in h:
        return True
    return False


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
        if all(_drainage_token_matches_identifier_word(w, text) for w in words):
            matched.append(f)
    if not matched:
        first_word = words[0]
        for f in features:
            props = f.get("properties") or {}
            hay = ((props.get("NAME") or "") + " " + (props.get("CODE") or "")).lower()
            if _drainage_token_matches_identifier_word(first_word, hay):
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
        words = re.findall(r"[A-Za-z]+|\d+", str(identifier))
        if len(words) >= 2:
            conditions: list[str] = []
            for w in words[:4]:
                sw = str(w).replace("'", "''")
                uw = sw.upper()
                if uw == "NO":
                    conditions.append(
                        "(UPPER(NAME) LIKE UPPER('%NO%') OR UPPER(NAME) LIKE UPPER('%NUMBER%'))"
                    )
                else:
                    conditions.append(f"UPPER(NAME) LIKE UPPER('%{sw}%')")
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


async def fetch_watershed_boundary(identifier: str) -> dict | None:
    data = await _fetch_district_boundary(
        LC_WATERSHEDS_URL,
        identifier,
        "SHED",
        "SHED",
        "SHED",
        "LC_WATERSHED",
        id_field_is_string=True,
        timeout=HTTP_TIMEOUT_WATERSHED,
    )
    return _ensure_feature_collection_wgs84(data)


async def fetch_subwatershed_boundary(identifier: str) -> dict | None:
    data = await _fetch_district_boundary(
        LC_SUBWATERSHEDS_URL,
        identifier,
        "SUB_BASIN",
        "SUB_BASIN",
        "SUB_BASIN,SHED",
        "LC_SUBWATERSHED",
        id_field_is_string=True,
        timeout=HTTP_TIMEOUT_WABDRAINAGE,
    )
    return _ensure_feature_collection_wgs84(data)


async def _fetch_polygons_union(
    base_url: str,
    where: str,
    result_record_count: int,
    timeout: float = HTTP_TIMEOUT_WABDRAINAGE,
) -> dict | None:
    query_url = f"{base_url}/query"
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": result_record_count,
    }
    try:
        client = _arcgis_client(timeout)
        data = await client.get(query_url, params, timeout)
    except Exception:
        return None
    if not data or "error" in data or not data.get("features"):
        return None
    data = _ensure_feature_collection_wgs84(data)
    if not data or not data.get("features"):
        return None
    geoms = []
    for feat in data["features"]:
        g = feat.get("geometry")
        if g and isinstance(g, dict) and g.get("coordinates"):
            try:
                geoms.append(shape(g))
            except Exception:
                pass
    if not geoms:
        return None
    union_geom = unary_union(geoms)
    if union_geom is None or union_geom.is_empty:
        return None
    if hasattr(union_geom, "__iter__") and not hasattr(union_geom, "exterior"):
        union_geom = unary_union(union_geom)
    geom_dict = None
    if hasattr(union_geom, "exterior") or hasattr(union_geom, "geoms"):
        geom_dict = mapping(union_geom)
    if not geom_dict:
        return None
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": geom_dict, "properties": {}}],
    }


async def fetch_soil_polygons(
    soil_code: str | None = None,
    hydric: bool | None = None,
) -> dict | None:
    conditions = []
    if soil_code and str(soil_code).strip():
        safe = str(soil_code).strip().replace("'", "''")
        conditions.append(f"UPPER(SOILCODE) LIKE UPPER('%{safe}%')")
    if hydric is True:
        conditions.append("HYDRIC = 'Y'")
    if not conditions:
        return None
    where = " AND ".join(conditions)
    return await _fetch_polygons_union(LC_SOILS_URL, where, 1000)


async def _fetch_soils_intersecting_geometry(geom_geojson: dict) -> list[str]:
    """Query soils layer for features intersecting the geometry. Returns unique SOILCODE values."""
    if not geom_geojson or not isinstance(geom_geojson, dict):
        return []
    parsed = _geojson_to_esri_for_spatial_query(geom_geojson)
    if not parsed:
        return []
    esri_geom, geom_type = parsed
    query_url = f"{LC_SOILS_URL}/query"
    form_data = {
        "where": "1=1",
        "outFields": "SOILCODE",
        "returnGeometry": "false",
        "returnDistinctValues": "true",
        "geometry": json.dumps(esri_geom),
        "geometryType": geom_type,
        "spatialRel": "esriSpatialRelIntersects",
        "f": "json",
        "resultRecordCount": "500",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_WABDRAINAGE)
        data = await client.post(query_url, form_data, HTTP_TIMEOUT_WABDRAINAGE)
    except Exception:
        return []
    if not data or "error" in data:
        return []
    features = data.get("features", [])
    codes = []
    for f in features:
        v = (f.get("attributes") or {}).get("SOILCODE")
        if v is not None and str(v).strip():
            codes.append(str(v).strip())
    return sorted(set(codes))


async def fetch_soil_polygons_intersecting_geometry(geom_geojson: dict) -> dict | None:
    """Fetch soil polygons that intersect the geometry. Returns GeoJSON FeatureCollection for map display."""
    if not geom_geojson or not isinstance(geom_geojson, dict):
        return None
    parsed = _geojson_to_esri_for_spatial_query(geom_geojson)
    if not parsed:
        return None
    esri_geom, geom_type = parsed
    query_url = f"{LC_SOILS_URL}/query"
    form_data = {
        "where": "1=1",
        "outFields": "SOILCODE,HYDRIC",
        "returnGeometry": "true",
        "outSR": str(ARCGIS_SRID),
        "geometry": json.dumps(esri_geom),
        "geometryType": geom_type,
        "spatialRel": "esriSpatialRelIntersects",
        "f": "geojson",
        "resultRecordCount": "500",
    }
    try:
        client = _arcgis_client(HTTP_TIMEOUT_WABDRAINAGE)
        data = await client.post(query_url, form_data, HTTP_TIMEOUT_WABDRAINAGE)
    except Exception:
        return None
    if not data or "error" in data or not data.get("features"):
        return None
    return _ensure_feature_collection_wgs84(data)


async def get_soil_types_for_project(
    project_name: str,
    radius_meters: float | None = None,
) -> dict[str, Any]:
    """
    Get soil types (SOILCODE) that intersect or are near a Lake County project.
    If radius_meters is given, creates a buffer around the project geometry.
    If not given, uses the project geometry directly (point/line/polygon).
    Returns: {found, project_name, soil_codes, radius_meters, error}
    """
    if not project_name or not str(project_name).strip():
        return {"found": False, "error": "project_name required", "soil_codes": []}
    result = await search_lake_county_project(str(project_name).strip())
    if not result.get("found") or not result.get("matches"):
        return {
            "found": False,
            "project_name": project_name,
            "soil_codes": [],
            "error": "No project found matching that name",
        }
    match = result["matches"][0]
    attrs = match.get("attributes") or {}
    name = attrs.get("Name", project_name)
    geom = match.get("geometry")
    if not geom or not isinstance(geom, dict):
        return {
            "found": True,
            "project_name": name,
            "soil_codes": [],
            "error": "Project has no geometry",
        }
    if radius_meters is not None and radius_meters > 0:
        if radius_meters > 5000:
            radius_meters = 5000
        geom = buffer_geometry_meters(geom, radius_meters)
        if not geom:
            return {
                "found": True,
                "project_name": name,
                "soil_codes": [],
                "radius_meters": radius_meters,
                "error": "Could not create buffer",
            }
    soil_codes = await _fetch_soils_intersecting_geometry(geom)
    soil_polygons_geojson = await fetch_soil_polygons_intersecting_geometry(geom)
    out: dict[str, Any] = {
        "found": True,
        "project_name": name,
        "soil_codes": soil_codes,
        "project_match": {
            "rep_point_geojson": match.get("rep_point_geojson"),
            "geometry_geojson": match.get("geometry_geojson"),
            "geojson": match.get("geometry_geojson") or match.get("rep_point_geojson"),
            "attributes": attrs,
        },
        "soil_polygons_geojson": soil_polygons_geojson,
    }
    if radius_meters is not None:
        out["radius_meters"] = radius_meters
    return out


async def fetch_flood_zone_polygons(
    flood_zone: str | None = None,
    zone_subtype: str | None = None,
    special_flood_hazard: bool | None = None,
) -> dict | None:
    conditions = []
    if flood_zone and str(flood_zone).strip():
        safe = str(flood_zone).strip().replace("'", "''")
        conditions.append(f"UPPER(FLD_ZONE) LIKE UPPER('%{safe}%')")
    if zone_subtype and str(zone_subtype).strip():
        raw = str(zone_subtype).strip()
        if raw.upper() == "REGULATORY FLOODWAY":
            raw = "FLOODWAY"
        safe = raw.replace("'", "''")
        conditions.append(f"UPPER(ZONE_SUBTY) LIKE UPPER('%{safe}%')")
    if special_flood_hazard is True:
        conditions.append("SFHA_TF = 'T'")
    if not conditions:
        return None
    where = " AND ".join(conditions)
    return await _fetch_polygons_union(LC_NFHL_FLOOD_ZONES_URL, where, 2000)


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
