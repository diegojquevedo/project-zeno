import json
from typing import Annotated, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.api.geo_lake_county_config import get_geo_lake_county_layer_by_id
from src.api.lake_county_constants import HTTP_TIMEOUT_QUERY
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.arcgis_layer_symbology import fetch_point_icons_for_class_field
from src.shared.logging_config import get_logger
from src.shared.map_constants import MAX_COLOR_CATEGORIES, MIN_COLOR_CATEGORIES
from src.shared.map_utils import (
    create_feature_layer_action,
    create_zoom_to_action,
    extract_unique_values,
    generate_color_palette,
)

logger = get_logger(__name__)


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_QUERY)


@tool("geo_query_layer")
async def geo_query_layer(
    layer_id: str,
    where: str = "1=1",
    geometry: Optional[str] = None,
    spatial_rel: str = "esriSpatialRelIntersects",
    out_fields: str = "*",
    limit: int = 1000,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Query an ArcGIS layer with WHERE clause and optional spatial filter.
    Use when data_source is geo_lake_county and you need to fetch features from a layer.

    Args:
        layer_id: Configured layer identifier
        where: SQL WHERE clause (e.g. "field_name='value'" or "code='ABC'")
        geometry: Optional GeoJSON geometry string for spatial filtering
        spatial_rel: Spatial relationship (esriSpatialRelIntersects, esriSpatialRelContains, esriSpatialRelWithin)
        out_fields: Comma-separated field names or "*" for all fields
        limit: Maximum number of features to return (default 1000)

    Returns GeoJSON FeatureCollection with matching features.
    """
    tid = tool_call_id or ""

    layer = get_geo_lake_county_layer_by_id(layer_id)
    if not layer:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Layer '{layer_id}' not found in configuration.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    url = layer.get("arcgis_url")
    if not url:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Layer '{layer_id}' has no URL configured.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    query_url = f"{url}/query" if not url.endswith("/query") else url

    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "f": "geojson",
        "resultRecordCount": limit,
    }

    if geometry:
        try:
            from shapely.geometry import shape

            geom_dict = (
                json.loads(geometry) if isinstance(geometry, str) else geometry
            )
            geom = shape(geom_dict)
            bounds = geom.bounds

            envelope = {
                "xmin": bounds[0],
                "ymin": bounds[1],
                "xmax": bounds[2],
                "ymax": bounds[3],
                "spatialReference": {"wkid": 4326},
            }

            params["geometry"] = json.dumps(envelope)
            params["geometryType"] = "esriGeometryEnvelope"
            params["spatialRel"] = spatial_rel
            params["inSR"] = "4326"
        except Exception as e:
            logger.warning("geo_query_layer_invalid_geometry", error=str(e))
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Invalid geometry provided: {str(e)}",
                            tool_call_id=tid,
                        )
                    ],
                },
            )

    client = _arcgis_client()

    try:
        if geometry:
            data = await client.post(query_url, params, HTTP_TIMEOUT_QUERY)
        else:
            data = await client.get(query_url, params, HTTP_TIMEOUT_QUERY)
    except Exception as e:
        logger.warning(
            "geo_query_layer_request_failed", url=query_url, error=str(e)
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to query layer '{layer_id}': {str(e)}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    if data.get("error"):
        error_msg = data["error"].get("message", "Unknown error")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"ArcGIS error querying '{layer_id}': {error_msg}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    features = data.get("features", [])
    feature_count = len(features)

    layer_name = layer.get("description", layer_id)
    where_display = where if where != "1=1" else "all"

    summary = f"Found {feature_count} feature(s) from {layer_name} (where: {where_display})"

    if geometry:
        summary += " with spatial filter applied"

    map_actions = []
    if feature_count > 0:
        value_field = layer.get("value_field")
        color_by_field = None
        color_palette = None
        if value_field:
            unique_values = extract_unique_values(data, value_field)
            if (
                MIN_COLOR_CATEGORIES <= len(unique_values) <= MAX_COLOR_CATEGORIES
            ):
                color_by_field = value_field
                color_palette = generate_color_palette(len(unique_values))

        point_icons = None
        point_icon_field = None
        vf = layer.get("value_field")
        if vf and layer.get("geometry_type") == "point":
            point_icons = await fetch_point_icons_for_class_field(
                client,
                url,
                str(vf),
                HTTP_TIMEOUT_QUERY,
            )
            if point_icons:
                point_icon_field = str(vf)

        map_actions.append(create_zoom_to_action(data))
        map_actions.append(
            create_feature_layer_action(
                geojson=data,
                label=f"{layer_name} ({feature_count} features)",
                color_by_field=color_by_field,
                color_palette=color_palette,
                point_icons_by_field_value=point_icons,
                point_icon_field=point_icon_field,
            )
        )

    return Command(
        update={
            "geo_query_result": {
                "layer_id": layer_id,
                "geojson": data,
                "feature_count": feature_count,
                "where": where,
                "has_geometry_filter": geometry is not None,
            },
            "map_actions": map_actions,
            "messages": [ToolMessage(content=summary, tool_call_id=tid)],
        },
    )
