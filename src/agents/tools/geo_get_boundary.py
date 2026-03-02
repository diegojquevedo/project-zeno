from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.api.geo_lake_county_config import get_geo_lake_county_layer_by_id
from src.api.lake_county_constants import HTTP_TIMEOUT_DOMAINS
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger
from src.shared.map_constants import BOUNDARY_ZOOM_FILL_OPACITY
from src.shared.map_utils import (
    create_boundary_layer_action,
    create_zoom_to_action,
)

logger = get_logger(__name__)


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_DOMAINS)


@tool("geo_get_boundary")
async def geo_get_boundary(
    layer_id: str,
    filter_field: str,
    filter_value: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Fetch the boundary geometry for a specific feature from a layer.
    Use when data_source is geo_lake_county and you need a boundary for spatial analysis.

    Args:
        layer_id: Configured layer identifier
        filter_field: Field name to filter by (e.g. "NAME", "CODE")
        filter_value: Value to match (e.g. "City of Waukegan", "103A")

    Returns boundary geometry as GeoJSON.
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

    where_clause = f"{filter_field}='{filter_value}'"

    params = {
        "where": where_clause,
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultRecordCount": 1,
    }

    client = _arcgis_client()

    try:
        data = await client.get(query_url, params, HTTP_TIMEOUT_DOMAINS)
    except Exception as e:
        logger.warning(
            "geo_get_boundary_request_failed", url=query_url, error=str(e)
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to fetch boundary from '{layer_id}': {str(e)}",
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
                        content=f"ArcGIS error fetching boundary from '{layer_id}': {error_msg}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    features = data.get("features", [])
    if not features or len(features) == 0:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"No feature found in '{layer_id}' with {filter_field}='{filter_value}'",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    feature = features[0]
    if not feature.get("geometry"):
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

    geometry = feature.get("geometry")
    properties = feature.get("properties", {})

    layer_name = layer.get("description", layer_id)
    label = properties.get(layer.get("label_field", "NAME"), filter_value)

    summary = f"Boundary found: {label} from {layer_name}"

    map_actions = [
        create_zoom_to_action(geometry),
        create_boundary_layer_action(
            geojson=data,
            label=f"Boundary: {label}",
            fill_opacity=BOUNDARY_ZOOM_FILL_OPACITY
        )
    ]

    return Command(
        update={
            "geo_boundary_result": {
                "layer_id": layer_id,
                "geojson": data,
                "geometry": geometry,
                "properties": properties,
                "label": label,
            },
            "map_actions": map_actions,
            "messages": [ToolMessage(content=summary, tool_call_id=tid)],
        },
    )
