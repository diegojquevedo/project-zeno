import asyncio
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.agents.custom_tools_registry import register_tool
from src.api.custom.geo_lake_county_projects_config import (
    GEO_PROJECT_CATEGORY_FLOOD_AUDITS,
    GEO_PROJECT_CATEGORY_PROJECTS,
    GEO_PROJECT_CATEGORY_STUDIES,
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
    ARCGIS_RESULT_RECORD_COUNT_BATCH,
    ARCGIS_SRID,
    HTTP_TIMEOUT_MUNICIPALITY,
    HTTP_TIMEOUT_QUERY,
)
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.lake_county_constants import LC_MUNICIPALITIES_URL
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

_MAX_RESULTS = 1000


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_QUERY)


async def _fetch_jurisdiction_boundary(jurisdiction: str) -> dict | None:
    safe = jurisdiction.strip().replace("'", "''")
    params = {
        "where": f"UPPER(NAME) LIKE UPPER('%{safe}%') OR UPPER(NAME1) LIKE UPPER('%{safe}%')",
        "outFields": "NAME,NAME1",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": 1,
    }
    try:
        client = ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(
            f"{LC_MUNICIPALITIES_URL}/query", params, HTTP_TIMEOUT_MUNICIPALITY
        )
    except Exception as e:
        logger.warning("geo_projects_jurisdiction_boundary_failed", jurisdiction=jurisdiction, error=str(e))
        return None
    if data.get("error") or not data.get("features"):
        return None
    return data


def _build_where_clause(
    project_category: str | None,
    project_types: list[str] | None,
    status: str | None,
    jurisdiction: str | None,
) -> str:
    conditions: list[str] = []

    if project_category:
        cat = project_category.strip().lower()
        if cat == GEO_PROJECT_CATEGORY_PROJECTS:
            conditions.append(
                "(projectsubtype IS NULL OR projectsubtype <> 'Flood Audit') "
                "AND (is_study IS NULL OR is_study = 0)"
            )
        elif cat == GEO_PROJECT_CATEGORY_STUDIES:
            conditions.append("is_study = 1")
        elif cat == GEO_PROJECT_CATEGORY_FLOOD_AUDITS:
            conditions.append("projectsubtype = 'Flood Audit'")

    if project_types:
        safe = [t.strip().replace("'", "''") for t in project_types if t and t.strip()]
        if safe:
            in_clause = ", ".join(f"'{t}'" for t in safe)
            conditions.append(f"projecttype IN ({in_clause})")

    if status:
        safe_s = status.strip().replace("'", "''")
        conditions.append(f"UPPER(status) LIKE UPPER('%{safe_s}%')")

    if jurisdiction:
        safe_j = jurisdiction.strip().replace("'", "''")
        conditions.append(f"UPPER(jurisdiction) LIKE UPPER('%{safe_j}%')")

    return " AND ".join(conditions) if conditions else "1=1"


async def _batch_fetch_geometries(
    client: ArcGISClient,
    project_ids_by_geom_type: dict[str, list[int]],
) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}

    async def _fetch_layer(geo_layer_key: str, pids: list[int]) -> None:
        url = GEO_PROJECT_LAYERS.get(geo_layer_key)
        if not url or not pids:
            return
        query_url = f"{url}/query"
        id_list = ",".join(str(p) for p in pids)
        form_data = {
            "where": f"{GEO_PROJECT_ID_FIELD} IN ({id_list})",
            "outFields": GEO_PROJECT_ID_FIELD,
            "returnGeometry": "true",
            "outSR": str(ARCGIS_SRID),
            "f": "geojson",
            "resultRecordCount": str(ARCGIS_RESULT_RECORD_COUNT_BATCH),
        }
        try:
            geojson = await client.post(query_url, form_data, HTTP_TIMEOUT_QUERY)
        except Exception as e:
            logger.warning(
                "geo_query_geo_projects_batch_failed",
                layer=geo_layer_key,
                count=len(pids),
                error=str(e),
            )
            return

        if geojson.get("error"):
            logger.warning(
                "geo_query_geo_projects_batch_arcgis_error",
                layer=geo_layer_key,
                error=geojson.get("error"),
            )
            return

        for feat in geojson.get("features", []):
            pid = feat.get("properties", {}).get(GEO_PROJECT_ID_FIELD)
            if pid is None:
                continue
            result.setdefault(pid, []).append(feat)

    await asyncio.gather(*[
        _fetch_layer(layer_key, pids)
        for layer_key, pids in project_ids_by_geom_type.items()
        if pids
    ])

    return result


@tool("geo_query_geo_projects")
async def geo_query_geo_projects(
    project_category: str = "projects",
    project_types: list[str] | None = None,
    status: str | None = None,
    jurisdiction: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Query Lake County stormwater projects in geo_lake_county mode.
    Fetches project attributes from the representative points layer, then fetches actual
    geometries (point, polyline, polygon) in parallel batches using project_id as join key.
    Emits map actions: one layer per geometry type + one layer for representative points.

    Args:
        project_category: Filter by category. One of: "projects" (normal projects, default),
            "studies" (is_study=1), "flood_audits" (projectsubtype='Flood Audit').
        project_types: List of projecttype values to filter (e.g. ["Capital", "WMB", "SIRF"]).
            Available: 319, Capital, Maintenance, Multiple Funding Sources, Other, SIRF, WMAG, WMB.
        status: Filter by project status (partial match, e.g. "Recommended", "Under Review").
        jurisdiction: Filter by municipality/jurisdiction name (partial match).
    """
    tid = tool_call_id or ""
    client = _arcgis_client()

    where = _build_where_clause(project_category, project_types, status, jurisdiction)

    jurisdiction_boundary = None
    if jurisdiction:
        jurisdiction_boundary = await _fetch_jurisdiction_boundary(jurisdiction)

    rep_query_url = f"{GEO_PROJECT_REPRESENTATIVE_POINTS_URL}/query"
    rep_params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": ARCGIS_SRID,
        "f": "geojson",
        "resultRecordCount": _MAX_RESULTS,
    }

    try:
        rep_data = await client.get(rep_query_url, rep_params, HTTP_TIMEOUT_QUERY)
    except Exception as e:
        logger.error("geo_query_geo_projects_rep_fetch_failed", error=str(e))
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to query projects: {str(e)}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    if rep_data.get("error"):
        error_msg = rep_data["error"].get("message", "Unknown error")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"ArcGIS error querying projects: {error_msg}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    rep_features = rep_data.get("features", [])
    if not rep_features:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="No projects found matching the given filters.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    project_ids_by_geom_type: dict[str, list[int]] = {}
    attrs_by_pid: dict[int, dict] = {}
    rep_features_by_pid: dict[int, dict] = {}

    for feat in rep_features:
        attrs = feat.get("properties", {})
        pid = attrs.get(GEO_PROJECT_ID_FIELD)
        geom_type_str = attrs.get(GEO_PROJECT_GEOMETRY_FIELD)
        if pid is not None:
            attrs_by_pid[pid] = attrs
            rep_features_by_pid[pid] = feat
        if pid is not None and geom_type_str:
            layer_key = GEO_PROJECT_GEOM_TYPE_TO_LAYER.get(geom_type_str)
            if layer_key:
                project_ids_by_geom_type.setdefault(layer_key, []).append(pid)

    geom_features_by_pid = await _batch_fetch_geometries(client, project_ids_by_geom_type)

    geom_features_with_projecttype: list[dict] = []
    rep_features_enriched: list[dict] = []

    for pid, attrs in attrs_by_pid.items():
        projecttype = attrs.get(GEO_PROJECT_TYPE_FIELD)
        color = (
            GEO_PROJECT_TYPE_COLORS.get(projecttype, GEO_PROJECT_DEFAULT_COLOR)
            if projecttype
            else GEO_PROJECT_DEFAULT_COLOR
        )

        for gfeat in geom_features_by_pid.get(pid, []):
            geom_features_with_projecttype.append({
                "type": "Feature",
                "geometry": gfeat.get("geometry"),
                "properties": {**attrs, "_color": color},
            })

        rep_feat = rep_features_by_pid.get(pid)
        if rep_feat:
            rep_features_enriched.append({
                "type": "Feature",
                "geometry": rep_feat.get("geometry"),
                "properties": {**attrs, "_color": color},
            })

    map_actions: list[dict] = []

    if jurisdiction_boundary and jurisdiction_boundary.get("features"):
        boundary_props = jurisdiction_boundary["features"][0].get("properties", {})
        boundary_label = boundary_props.get("NAME1") or boundary_props.get("NAME") or jurisdiction
        map_actions.append({
            "type": "addBoundaryLayer",
            "geojson": jurisdiction_boundary,
            "label": f"Jurisdiction: {boundary_label}",
        })

    if geom_features_with_projecttype:
        map_actions.append({
            "type": "addProjectGeometryLayer",
            "geojson": {"type": "FeatureCollection", "features": geom_features_with_projecttype},
            "label": "Project Geometries",
            "colorByField": GEO_PROJECT_TYPE_FIELD,
            "colorMap": GEO_PROJECT_TYPE_COLORS,
            "defaultColor": GEO_PROJECT_DEFAULT_COLOR,
        })

    if rep_features_enriched:
        map_actions.append({
            "type": "addProjectRepPointsLayer",
            "geojson": {"type": "FeatureCollection", "features": rep_features_enriched},
            "label": "Project Reference Points",
            "colorByField": GEO_PROJECT_TYPE_FIELD,
            "colorMap": GEO_PROJECT_TYPE_COLORS,
            "defaultColor": GEO_PROJECT_DEFAULT_COLOR,
        })

    total = len(rep_features)
    with_geom = len(geom_features_with_projecttype)

    summary_parts = [f"Found {total} project(s)"]
    if project_category and project_category != "projects":
        summary_parts.append(f"category: {project_category}")
    if project_types:
        summary_parts.append(f"types: {', '.join(project_types)}")
    if status:
        summary_parts.append(f"status: {status}")
    if jurisdiction:
        summary_parts.append(f"jurisdiction: {jurisdiction}")
    summary_parts.append(
        f"{with_geom} with actual geometry, {total - with_geom} reference points only"
    )

    return Command(
        update={
            "map_actions": map_actions,
            "messages": [ToolMessage(content=". ".join(summary_parts), tool_call_id=tid)],
        },
    )


register_tool(geo_query_geo_projects)
