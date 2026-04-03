from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.agents.custom_tools_registry import register_tool
from src.api.custom.geo_lake_county_projects_config import (
    GEO_PROJECT_DEFAULT_COLOR,
    GEO_PROJECT_GEOM_TYPE_TO_LAYER,
    GEO_PROJECT_GEOMETRY_FIELD,
    GEO_PROJECT_ID_FIELD,
    GEO_PROJECT_LAYERS,
    GEO_PROJECT_REPRESENTATIVE_POINTS_URL,
    GEO_PROJECT_TYPE_COLORS,
    GEO_PROJECT_TYPE_FIELD,
)
from src.api.lake_county_constants import (
    ARCGIS_SRID,
    HTTP_TIMEOUT_QUERY,
)
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger
from src.shared.map_utils import create_zoom_to_action

logger = get_logger(__name__)


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_QUERY)


@tool("geo_get_project_geometry")
async def geo_get_project_geometry(
    project_name: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Find a stormwater project by name. Returns project attributes and displays its geometry on the map.
    Stores the geometry in state for optional use in geo_spatial_intersection.

    Use when the user asks about a specific project by name:
    - "Give me info about Wadsworth Oaks" → returns attributes and shows geometry on map
    - "Soils in Wadsworth Oaks project" → call this first, then geo_spatial_intersection

    When the user only wants project info, summarize the returned attributes. Do NOT call
    geo_spatial_intersection unless the user explicitly wants features within the project.

    Args:
        project_name: Name of the project to search for (partial match).
    """
    tid = tool_call_id or ""
    client = _arcgis_client()

    safe_name = project_name.strip().replace("'", "''")
    rep_params = {
        "where": f"UPPER(Name) LIKE UPPER('%{safe_name}%')",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": str(ARCGIS_SRID),
        "f": "geojson",
        "resultRecordCount": 5,
    }

    rep_query_url = f"{GEO_PROJECT_REPRESENTATIVE_POINTS_URL}/query"
    try:
        rep_data = await client.get(
            rep_query_url,
            rep_params,
            HTTP_TIMEOUT_QUERY,
        )
    except Exception as e:
        logger.error(
            "geo_get_project_geometry_rep_failed",
            error=str(e),
            query_url=rep_query_url,
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to search for project '{project_name}': {str(e)}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    if rep_data.get("error") or not rep_data.get("features"):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"No project found matching '{project_name}'.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    rep_features = rep_data["features"]
    matched = rep_features[0]
    matched_name = matched.get("properties", {}).get("Name", project_name)

    project_ids_by_geom_type: dict[str, list[int]] = {}
    for feat in rep_features:
        props = feat.get("properties", {})
        pid = props.get(GEO_PROJECT_ID_FIELD)
        geom_type_str = props.get(GEO_PROJECT_GEOMETRY_FIELD)
        if pid is not None and geom_type_str:
            layer_key = GEO_PROJECT_GEOM_TYPE_TO_LAYER.get(geom_type_str)
            if layer_key:
                project_ids_by_geom_type.setdefault(layer_key, []).append(pid)

    geometry_features: list[dict] = []

    for layer_key, pids in project_ids_by_geom_type.items():
        url = GEO_PROJECT_LAYERS.get(layer_key)
        if not url or not pids:
            continue
        id_list = ",".join(str(p) for p in pids)
        form_data = {
            "where": f"{GEO_PROJECT_ID_FIELD} IN ({id_list})",
            "outFields": GEO_PROJECT_ID_FIELD,
            "returnGeometry": "true",
            "outSR": str(ARCGIS_SRID),
            "f": "geojson",
            "resultRecordCount": "50",
        }
        try:
            geojson = await client.post(f"{url}/query", form_data, HTTP_TIMEOUT_QUERY)
            geometry_features.extend(geojson.get("features", []))
        except Exception as e:
            logger.warning(
                "geo_get_project_geometry_geom_fetch_failed",
                layer=layer_key,
                error=str(e),
            )

    if not geometry_features:
        geometry_features = [
            {
                "type": "Feature",
                "geometry": matched.get("geometry"),
                "properties": matched.get("properties", {}),
            }
        ]

    geojson_result = {"type": "FeatureCollection", "features": geometry_features}

    geo_project_geometry = {
        "project_name": matched_name,
        "geojson": geojson_result,
    }

    props = matched.get("properties", {})
    skip_keys = {"OBJECTID", "GlobalID", "Shape__Area", "Shape__Length", GEO_PROJECT_GEOMETRY_FIELD}
    attrs = {k: v for k, v in props.items() if v is not None and str(v).strip() and k not in skip_keys}
    attr_lines = "\n".join(f"- {k}: {v}" for k, v in sorted(attrs.items()))

    projecttype = props.get(GEO_PROJECT_TYPE_FIELD)
    color = (
        GEO_PROJECT_TYPE_COLORS.get(projecttype, GEO_PROJECT_DEFAULT_COLOR)
        if projecttype
        else GEO_PROJECT_DEFAULT_COLOR
    )
    attrs_with_color = {**attrs, "_color": color}

    geom_features_with_projecttype = [
        {
            "type": "Feature",
            "geometry": gfeat.get("geometry"),
            "properties": attrs_with_color,
        }
        for gfeat in geometry_features
    ]

    rep_point = matched.get("geometry")
    rep_features_enriched = []
    if rep_point and rep_point.get("type") == "Point":
        rep_features_enriched = [
            {
                "type": "Feature",
                "geometry": rep_point,
                "properties": attrs_with_color,
            }
        ]

    map_actions = [create_zoom_to_action(geojson_result)]
    if geom_features_with_projecttype:
        map_actions.append({
            "type": "addProjectGeometryLayer",
            "geojson": {"type": "FeatureCollection", "features": geom_features_with_projecttype},
            "label": f"Project: {matched_name}",
            "colorByField": GEO_PROJECT_TYPE_FIELD,
            "colorMap": GEO_PROJECT_TYPE_COLORS,
            "defaultColor": GEO_PROJECT_DEFAULT_COLOR,
        })
    if rep_features_enriched:
        map_actions.append({
            "type": "addProjectRepPointsLayer",
            "geojson": {"type": "FeatureCollection", "features": rep_features_enriched},
            "label": f"Reference point: {matched_name}",
            "colorByField": GEO_PROJECT_TYPE_FIELD,
            "colorMap": GEO_PROJECT_TYPE_COLORS,
            "defaultColor": GEO_PROJECT_DEFAULT_COLOR,
        })

    content = (
        f"Found project '{matched_name}' with {len(geometry_features)} geometry feature(s). "
        "Geometry is displayed on the map.\n\nProject attributes:\n"
        f"{attr_lines}\n\n"
        "If the user wants features within this project (soils, streams, flood zones, etc.), "
        "call geo_spatial_intersection with where_layer_id='geo_project_geometry'. "
        "If the user only wanted project info, summarize the attributes above."
    )

    return Command(
        update={
            "geo_project_geometry": geo_project_geometry,
            "map_actions": map_actions,
            "messages": [ToolMessage(content=content, tool_call_id=tid)],
        },
    )


register_tool(geo_get_project_geometry)
