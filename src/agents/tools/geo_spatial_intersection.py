import json
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command
from shapely.geometry import shape

from src.api.geo_lake_county_config import get_geo_lake_county_layer_by_id
from src.api.lake_county_constants import HTTP_TIMEOUT_DOMAINS
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

logger = get_logger(__name__)


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_DOMAINS)


def _build_flexible_where_clause(field: str, value: str) -> str:
    normalized = value.strip()
    return f"UPPER({field}) LIKE UPPER('%{normalized}%')"


def _geojson_geometry_to_esri(geojson_geom: dict) -> dict | None:
    geom_type = geojson_geom.get("type", "")
    coordinates = geojson_geom.get("coordinates")

    if not coordinates:
        return None

    if geom_type == "Polygon":
        return {
            "rings": coordinates,
            "spatialReference": {"wkid": 4326},
        }

    if geom_type == "MultiPolygon":
        rings = []
        for polygon in coordinates:
            rings.extend(polygon)
        return {
            "rings": rings,
            "spatialReference": {"wkid": 4326},
        }

    return None


async def _fetch_boundary(
    client: ArcGISClient,
    query_url: str,
    filter_field: str,
    filter_value: str,
) -> tuple[dict | None, str | None]:
    exact_clause = f"{filter_field}='{filter_value}'"
    params = {
        "where": exact_clause,
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultRecordCount": 1,
    }

    try:
        data = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
    except Exception as e:
        return None, str(e)

    if data.get("error") or not data.get("features"):
        flexible_clause = _build_flexible_where_clause(filter_field, filter_value)
        params["where"] = flexible_clause
        params["resultRecordCount"] = 5

        try:
            data = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
        except Exception as e:
            return None, str(e)

    if data.get("error"):
        return None, data["error"].get("message", "Unknown ArcGIS error")

    features = data.get("features", [])
    if not features:
        return None, None

    return data, None


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
) -> Command:
    """
    Perform spatial intersection between two layers: WHERE (boundary) and WHAT (features).
    Use when data_source is geo_lake_county for bidirectional queries like:
    - "Show [feature types] in [location]" (WHERE=locations, WHAT=features)
    - "Show [locations] with [feature type]" (WHERE=features, WHAT=locations)

    Args:
        where_layer_id: Layer id defining the boundary (e.g. "locations", "regions")
        where_filter_field: Field to filter WHERE layer (e.g. "NAME", "CODE"). Discovered from schema.
        where_filter_value: Value for WHERE filter (e.g. location name, code)
        what_layer_id: Layer id to query features from (e.g. "features", "types")
        what_where_clause: Optional WHERE clause for WHAT layer (e.g. "TYPE='ABC'" or "CATEGORY='X'")
        what_color_field: Field from WHAT layer schema to use for color-coding features. Leave empty for no color-coding. Discovered from schema — use a categorical field with meaningful distinct values.
        spatial_rel: Spatial relationship (default: esriSpatialRelIntersects)

    Returns both the boundary and intersecting features as GeoJSON.
    """
    tid = tool_call_id or ""

    where_layer = get_geo_lake_county_layer_by_id(where_layer_id)
    what_layer = get_geo_lake_county_layer_by_id(what_layer_id)

    if not where_layer:
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

    if not what_layer:
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

    where_url = where_layer.get("arcgis_url")
    what_url = what_layer.get("arcgis_url")

    if not where_url or not what_url:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="One or both layers have no URL configured.",
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
    boundary_geometry = boundary_features[0].get("geometry")
    boundary_properties = boundary_features[0].get("properties", {})

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

    what_query_url = (
        f"{what_url}/query" if not what_url.endswith("/query") else what_url
    )

    esri_polygon = _geojson_geometry_to_esri(boundary_geometry)

    if esri_polygon:
        what_params = {
            "where": what_where_clause,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "geometry": json.dumps(esri_polygon),
            "geometryType": "esriGeometryPolygon",
            "spatialRel": spatial_rel,
            "inSR": "4326",
            "resultRecordCount": 2000,
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
        what_params = {
            "where": what_where_clause,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "geometry": json.dumps(envelope),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": spatial_rel,
            "inSR": "4326",
            "resultRecordCount": 2000,
        }

    try:
        what_data = await client.post(
            what_query_url, what_params, HTTP_TIMEOUT_DOMAINS
        )

    except Exception as e:
        logger.error("geo_spatial_intersection_failed", error=str(e))
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to query '{what_layer_id}' features: {str(e)}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    if what_data.get("error"):
        error_msg = what_data["error"].get("message", "Unknown error")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"ArcGIS error querying '{what_layer_id}': {error_msg}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    what_features = what_data.get("features", [])
    what_count = len(what_features)

    where_name = where_layer.get("description", where_layer_id)
    what_name = what_layer.get("description", what_layer_id)
    boundary_label = boundary_properties.get(where_filter_field, where_filter_value)

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

    return Command(
        update={
            "geo_spatial_intersection_result": {
                "where_layer_id": where_layer_id,
                "what_layer_id": what_layer_id,
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
