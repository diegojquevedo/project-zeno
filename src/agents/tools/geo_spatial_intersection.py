import json
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from shapely.geometry import shape

from src.api.geo_lake_county_config import (
    get_geo_lake_county_layer_by_id,
    normalize_geo_lake_county_layer_id,
)
from src.api.lake_county_constants import (
    HTTP_TIMEOUT_DOMAINS,
    HTTP_TIMEOUT_QUERY,
)
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger
from src.shared.map_constants import MAX_COLOR_CATEGORIES, MIN_COLOR_CATEGORIES
from src.shared.map_utils import (
    create_boundary_layer_action,
    create_feature_layer_action,
    create_zoom_to_action,
    extract_unique_values,
    generate_color_palette,
)

_PROJECT_GEOMETRY_SENTINEL = "geo_project_geometry"

logger = get_logger(__name__)

_PAGE_SIZE = 1000
_MAX_PAGES = 20


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_QUERY)


def _build_flexible_where_clause(field: str, value: str) -> str:
    normalized = value.strip().replace("'", "''")
    return f"{field} LIKE '%{normalized}%'"


def _geojson_geometry_to_esri(geojson_geom: dict) -> dict | None:
    geom_type = geojson_geom.get("type", "")
    coordinates = geojson_geom.get("coordinates")

    if geom_type == "Polygon" and coordinates:
        return {
            "rings": coordinates,
            "spatialReference": {"wkid": 4326},
        }

    if geom_type == "MultiPolygon" and coordinates:
        rings = []
        for polygon in coordinates:
            rings.extend(polygon)
        return {
            "rings": rings,
            "spatialReference": {"wkid": 4326},
        }

    if geom_type == "GeometryCollection":
        rings = []
        for geom in geojson_geom.get("geometries", []):
            sub = _geojson_geometry_to_esri(geom)
            if sub and "rings" in sub:
                rings.extend(sub["rings"])
        if rings:
            return {"rings": rings, "spatialReference": {"wkid": 4326}}

    return None


async def _fetch_what_page(
    client: ArcGISClient,
    query_url: str,
    base_params: dict,
    offset: int,
) -> dict:
    params = {**base_params, "resultOffset": offset, "resultRecordCount": _PAGE_SIZE}
    try:
        return await client.post(query_url, params, HTTP_TIMEOUT_QUERY)
    except Exception as e:
        logger.warning("geo_spatial_intersection_page_failed", offset=offset, error=str(e))
        return {}


async def _fetch_all_what_features(
    client: ArcGISClient,
    query_url: str,
    base_params: dict,
) -> tuple[list[dict], bool]:
    all_features: list[dict] = []
    had_error = False

    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        data = await _fetch_what_page(client, query_url, base_params, offset)

        if not data:
            had_error = True
            break

        if data.get("error"):
            logger.warning(
                "geo_spatial_intersection_arcgis_error",
                offset=offset,
                error=data.get("error"),
            )
            had_error = True
            break

        page_features = data.get("features", [])
        all_features.extend(page_features)

        logger.info(
            "geo_spatial_intersection_page_fetched",
            offset=offset,
            count=len(page_features),
            total_so_far=len(all_features),
        )

        if not data.get("exceededTransferLimit", False):
            break

        if len(page_features) < _PAGE_SIZE:
            break

    return all_features, had_error


def _build_fallback_clauses(filter_field: str, filter_value: str) -> list[str]:
    stripped = filter_value.strip().replace("'", "''")
    if stripped.lstrip("-").isdigit():
        return [
            f"{filter_field} = {stripped}",
            f"{filter_field} LIKE '{stripped}'",
            f"CAST({filter_field} AS VARCHAR(20)) = '{stripped}'",
        ]
    return [
        f"{filter_field} LIKE '%{stripped}%'",
        f"UPPER({filter_field}) LIKE UPPER('%{stripped}%')",
    ]


async def _fetch_boundary(
    client: ArcGISClient,
    query_url: str,
    filter_field: str,
    filter_value: str,
) -> tuple[dict | None, str | None]:
    exact_clause = f"{filter_field}='{filter_value}'"
    probe_params: dict = {
        "where": exact_clause,
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",
        "resultRecordCount": 1,
    }

    try:
        probe = await client.get(query_url, probe_params, HTTP_TIMEOUT_DOMAINS)
    except Exception as e:
        return None, str(e)

    where_clause = exact_clause if not probe.get("error") and probe.get("features") else None
    if where_clause is None:
        for fallback_clause in _build_fallback_clauses(filter_field, filter_value):
            probe_params["where"] = fallback_clause
            try:
                probe = await client.get(query_url, probe_params, HTTP_TIMEOUT_DOMAINS)
            except Exception as e:
                return None, str(e)
            if not probe.get("error") and probe.get("features"):
                where_clause = fallback_clause
                break

    if probe.get("error") and where_clause is None:
        return None, probe["error"].get("message", "Unknown ArcGIS error")

    if where_clause is None:
        return None, None

    all_features: list[dict] = []
    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        page_params = {
            "where": where_clause,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326",
            "resultRecordCount": _PAGE_SIZE,
            "resultOffset": offset,
        }
        try:
            data = await client.get(query_url, page_params, HTTP_TIMEOUT_DOMAINS)
        except Exception as e:
            return None, str(e)
        if data.get("error"):
            return None, data["error"].get("message", "Unknown ArcGIS error")
        page_features = data.get("features", [])
        all_features.extend(page_features)
        if not data.get("exceededTransferLimit", False):
            break
        if len(page_features) < _PAGE_SIZE:
            break

    if not all_features:
        return None, None

    merged: dict = {"type": "FeatureCollection", "features": all_features}
    return merged, None


def _union_geometry_from_fc(geojson_fc: dict) -> dict | None:
    features = geojson_fc.get("features", [])
    if not features:
        return None

    polygon_geom_types = {"Polygon", "MultiPolygon"}

    polygon_features = [f for f in features if f.get("geometry", {}).get("type") in polygon_geom_types]
    candidates = polygon_features if polygon_features else features

    if len(candidates) == 1:
        return candidates[0].get("geometry")

    try:
        from shapely.ops import unary_union
        shapes = [shape(f["geometry"]) for f in candidates if f.get("geometry")]
        if not shapes:
            return None
        unioned = unary_union(shapes)
        geom = unioned.__geo_interface__
        if geom.get("type") not in ("Polygon", "MultiPolygon", "GeometryCollection"):
            return geom
        return json.loads(json.dumps(geom))
    except Exception:
        return candidates[0].get("geometry")


@tool("geo_spatial_intersection")
async def geo_spatial_intersection(
    where_layer_id: str,
    where_filter_field: str,
    where_filter_value: str,
    what_layer_id: str,
    what_where_clause: str = "1=1",
    what_color_field: str = "",
    spatial_rel: str = "esriSpatialRelIntersects",
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict[str, Any], InjectedState] = None,
) -> Command:
    """
    Perform spatial intersection between two layers: WHERE (boundary) and WHAT (features).
    Use when data_source is geo_lake_county for bidirectional queries like:
    - "Show [feature types] in [location]" (WHERE=locations, WHAT=features)
    - "Show [locations] with [feature type]" (WHERE=features, WHAT=locations)

    SPECIAL: when where_layer_id="geo_project_geometry", the boundary is taken from the
    geo_project_geometry stored in state by a prior geo_get_project_geometry call.
    In that case, where_filter_field should be "" and where_filter_value is the project name label.

    Args:
        where_layer_id: Layer id defining the boundary (e.g. "locations", "regions"),
            or "geo_project_geometry" to use a project's geometry stored in state.
        where_filter_field: Field to filter WHERE layer (e.g. "NAME", "CODE"). Discovered from schema.
            Leave empty when using "geo_project_geometry" sentinel.
        where_filter_value: Value for WHERE filter (e.g. location name, code).
            When using "geo_project_geometry", pass the project name as a label.
        what_layer_id: Catalog layer id to query (e.g. "soils", "hydro_lines", "representative_points"
            for Lake County projects). Use representative_points for SMC project points — not ArcGIS service names.
        what_where_clause: Optional WHERE clause for WHAT layer (e.g. "TYPE='ABC'" or "CATEGORY='X'")
        what_color_field: Field from WHAT layer schema to use for color-coding features. Leave empty for no color-coding. Discovered from schema — use a categorical field with meaningful distinct values.
        spatial_rel: Spatial relationship (default: esriSpatialRelIntersects)

    Returns both the boundary and intersecting features as GeoJSON.
    """
    tid = tool_call_id or ""
    state = state or {}

    logger.info(
        "DEBUG_SPATIAL_INTERSECTION: invoke",
        where_layer_id=where_layer_id,
        what_layer_id=what_layer_id,
    )

    using_project_geometry = (
        str(where_layer_id).strip() == _PROJECT_GEOMETRY_SENTINEL
    )

    if using_project_geometry:
        geo_project_geometry: dict | None = state.get("geo_project_geometry")
        if not geo_project_geometry:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                "No project geometry in state. "
                                "Call geo_get_project_geometry first to find and store the project geometry."
                            ),
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        project_geojson_fc = geo_project_geometry.get("geojson", {})
        project_name_label = geo_project_geometry.get("project_name", where_filter_value)

        boundary_geometry = _union_geometry_from_fc(project_geojson_fc)
        if not boundary_geometry:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Project geometry for '{project_name_label}' is empty or invalid.",
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        boundary_data = project_geojson_fc
        boundary_properties: dict = {}
        boundary_label = project_name_label
        where_name = "Project"
    else:
        where_norm = normalize_geo_lake_county_layer_id(where_layer_id)
        if where_norm != str(where_layer_id).strip():
            logger.info(
                "DEBUG_SPATIAL_INTERSECTION: where_layer_id_normalized",
                raw=where_layer_id,
                normalized=where_norm,
            )
        where_layer = get_geo_lake_county_layer_by_id(where_layer_id)
        if not where_layer:
            logger.warning(
                "DEBUG_SPATIAL_INTERSECTION: where_layer_missing",
                where_layer_id=where_layer_id,
                normalized=where_norm,
            )
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"WHERE layer '{where_layer_id}' not found in configuration.",
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        where_url = where_layer.get("arcgis_url")
        if not where_url:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="WHERE layer has no URL configured.",
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        client = _arcgis_client()
        where_query_url = (
            f"{where_url}/query" if not where_url.endswith("/query") else where_url
        )

        boundary_data, fetch_error = await _fetch_boundary(
            client, where_query_url, where_filter_field, where_filter_value
        )

        if fetch_error:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Failed to fetch boundary from '{where_layer_id}': {fetch_error}",
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        if boundary_data is None:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"No boundary found in '{where_layer_id}' "
                                f"where {where_filter_field} matches '{where_filter_value}'. "
                                "Try discovering the schema to verify available fields and actual values."
                            ),
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        boundary_features = boundary_data.get("features", [])
        boundary_geometry = _union_geometry_from_fc(boundary_data)
        boundary_properties = (
            boundary_features[0].get("properties", {}) if boundary_features else {}
        )

        if not boundary_geometry:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="Boundary feature has no geometry.",
                            tool_call_id=tid,
                        )
                    ],
                },
            )

        where_name = where_layer.get("description", where_layer_id)
        boundary_label = boundary_properties.get(where_filter_field, where_filter_value)

    what_norm = normalize_geo_lake_county_layer_id(what_layer_id)
    if what_norm != str(what_layer_id).strip():
        logger.info(
            "DEBUG_SPATIAL_INTERSECTION: what_layer_id_normalized",
            raw=what_layer_id,
            normalized=what_norm,
        )
    what_layer = get_geo_lake_county_layer_by_id(what_layer_id)
    if not what_layer:
        logger.warning(
            "DEBUG_SPATIAL_INTERSECTION: what_layer_missing",
            what_layer_id=what_layer_id,
            normalized=what_norm,
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"WHAT layer '{what_layer_id}' not found in configuration.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    what_url = what_layer.get("arcgis_url")
    if not what_url:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="WHAT layer has no URL configured.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    client = _arcgis_client()
    what_query_url = (
        f"{what_url}/query" if not what_url.endswith("/query") else what_url
    )

    esri_polygon = _geojson_geometry_to_esri(boundary_geometry)

    if esri_polygon:
        what_base_params = {
            "where": what_where_clause,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "geometry": json.dumps(esri_polygon),
            "geometryType": "esriGeometryPolygon",
            "spatialRel": spatial_rel,
            "inSR": "4326",
        }
    else:
        geom = shape(boundary_geometry)
        bounds = geom.bounds
        envelope = {
            "xmin": bounds[0],
            "ymin": bounds[1],
            "xmax": bounds[2],
            "ymax": bounds[3],
            "spatialReference": {"wkid": 4326},
        }
        what_base_params = {
            "where": what_where_clause,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "geometry": json.dumps(envelope),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": spatial_rel,
            "inSR": "4326",
        }

    what_features, fetch_had_error = await _fetch_all_what_features(
        client, what_query_url, what_base_params
    )

    if fetch_had_error and not what_features:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to query '{what_layer_id}' features.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    what_count = len(what_features)
    what_data = {"type": "FeatureCollection", "features": what_features}

    what_name = what_layer.get("description", what_layer_id)

    summary = f"Found {what_count} feature(s) from {what_name} intersecting {boundary_label} ({where_name})"
    if what_where_clause != "1=1":
        summary += f" with filter: {what_where_clause}"

    map_actions = []

    map_actions.append(create_zoom_to_action(boundary_data))

    map_actions.append(create_boundary_layer_action(
        geojson=boundary_data,
        label=f"Boundary: {boundary_label}"
    ))

    if what_count > 0:
        color_by_field = what_color_field if what_color_field else None
        color_palette = None

        if color_by_field:
            unique_values = extract_unique_values(what_data, color_by_field)
            unique_count = len(unique_values)
            if (unique_count >= MIN_COLOR_CATEGORIES
                and unique_count <= MAX_COLOR_CATEGORIES):
                color_palette = generate_color_palette(unique_count)

        action = create_feature_layer_action(
            geojson=what_data,
            label=f"{what_name} in {boundary_label}",
            color_by_field=color_by_field,
            color_palette=color_palette
        )

        map_actions.append(action)

    where_result_id = (
        str(where_layer_id).strip()
        if using_project_geometry
        else normalize_geo_lake_county_layer_id(where_layer_id)
    )
    what_result_id = normalize_geo_lake_county_layer_id(what_layer_id)

    return Command(
        update={
            "geo_spatial_intersection_result": {
                "where_layer_id": where_result_id,
                "what_layer_id": what_result_id,
                "boundary_geojson": boundary_data,
                "boundary_geometry": boundary_geometry,
                "boundary_label": boundary_label,
                "what_geojson": what_data,
                "what_count": what_count,
            },
            "map_actions": map_actions,
            "messages": [ToolMessage(content=summary, tool_call_id=tid)],
        },
    )
