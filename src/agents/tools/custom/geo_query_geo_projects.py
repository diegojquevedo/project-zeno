import asyncio
import json
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.agents.custom_tools_registry import register_tool
from src.agents.tools.geo_build_result_summary import _build_charts_from_rows
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
from src.api.geo_lake_county_config import get_geo_lake_county_layer_by_id
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


async def _fetch_layer_boundary(
    layer_id: str,
    filter_field: str,
    filter_value: str,
) -> dict | None:
    layer = get_geo_lake_county_layer_by_id(layer_id)
    if not layer:
        logger.warning("geo_projects_boundary_layer_not_found", layer_id=layer_id)
        return None
    url = layer.get("arcgis_url")
    if not url:
        return None
    query_url = f"{url}/query" if not url.endswith("/query") else url
    safe_value = filter_value.strip().replace("'", "''")
    params = {
        "where": f"{filter_field}='{safe_value}'",
        "outFields": filter_field,
        "returnGeometry": "true",
        "outSR": str(ARCGIS_SRID),
        "f": "geojson",
        "resultRecordCount": 1,
    }
    try:
        client = ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_MUNICIPALITY)
        data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
    except Exception as e:
        logger.warning(
            "geo_projects_layer_boundary_failed",
            layer_id=layer_id,
            filter_field=filter_field,
            filter_value=filter_value,
            error=str(e),
        )
        return None
    if data.get("error") or not data.get("features"):
        stripped = filter_value.strip().replace("'", "''")
        if stripped.lstrip("-").isdigit():
            fallback_clauses = [
                f"{filter_field} = {stripped}",
                f"{filter_field} LIKE '{stripped}'",
                f"CAST({filter_field} AS VARCHAR(20)) = '{stripped}'",
            ]
        else:
            fallback_clauses = [
                f"{filter_field} LIKE '%{stripped}%'",
                f"UPPER({filter_field}) LIKE UPPER('%{stripped}%')",
            ]

        for clause in fallback_clauses:
            fallback_params = {**params, "where": clause}
            try:
                client2 = ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_MUNICIPALITY)
                data = await client2.get(query_url, fallback_params, HTTP_TIMEOUT_MUNICIPALITY)
            except Exception as e:
                logger.warning(
                    "geo_projects_layer_boundary_flexible_failed",
                    layer_id=layer_id,
                    clause=clause,
                    error=str(e),
                )
                continue
            if not data.get("error") and data.get("features"):
                break

    if data.get("error") or not data.get("features"):
        return None
    return data


async def _fetch_municipality_boundary(jurisdiction: str) -> dict | None:
    if not jurisdiction or not jurisdiction.strip():
        return None
    safe = jurisdiction.strip().replace("'", "''")
    query_url = f"{LC_MUNICIPALITIES_URL}/query"
    for clause in [
        f"NAME LIKE '%{safe}%'",
        f"NAME1 LIKE '%{safe}%'",
    ]:
        params = {
            "where": clause,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": str(ARCGIS_SRID),
            "f": "geojson",
            "resultRecordCount": 1,
        }
        try:
            client = ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_MUNICIPALITY)
            data = await client.get(query_url, params, HTTP_TIMEOUT_MUNICIPALITY)
        except Exception as e:
            logger.warning("geo_projects_municipality_boundary_failed", jurisdiction=jurisdiction, error=str(e))
            continue
        if not data.get("error") and data.get("features"):
            return data
    return None


def _geojson_geometry_to_esri(geojson_geom: dict) -> dict | None:
    geom_type = geojson_geom.get("type", "")
    coordinates = geojson_geom.get("coordinates")
    if not coordinates:
        return None
    if geom_type == "Polygon":
        return {"rings": coordinates, "spatialReference": {"wkid": 4326}}
    if geom_type == "MultiPolygon":
        rings = []
        for polygon in coordinates:
            rings.extend(polygon)
        return {"rings": rings, "spatialReference": {"wkid": 4326}}
    return None


def _build_category_clause(project_category: str | None) -> str | None:
    if not project_category:
        return None
    cat = project_category.strip().lower()
    if cat == GEO_PROJECT_CATEGORY_PROJECTS:
        return (
            "(projectsubtype IS NULL OR projectsubtype <> 'Flood Audit') "
            "AND (is_study IS NULL OR is_study = 0)"
        )
    if cat == GEO_PROJECT_CATEGORY_STUDIES:
        return "is_study = 1"
    if cat == GEO_PROJECT_CATEGORY_FLOOD_AUDITS:
        return "projectsubtype = 'Flood Audit'"
    return None


def _combine_where(
    project_category: str | None,
    where_clause: str | None,
    jurisdiction: str | None = None,
) -> str:
    parts: list[str] = []
    category_clause = _build_category_clause(project_category)
    if category_clause:
        parts.append(category_clause)
    if jurisdiction and jurisdiction.strip():
        safe = jurisdiction.strip().replace("'", "''")
        parts.append(f"(UPPER(jurisdiction) LIKE UPPER('%{safe}%'))")
    if where_clause and where_clause.strip() and where_clause.strip() != "1=1":
        parts.append(f"({where_clause.strip()})")
    return " AND ".join(parts) if parts else "1=1"


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
    where_clause: str = "1=1",
    project_category: str = "projects",
    jurisdiction: str | None = None,
    boundary_layer_id: str | None = None,
    boundary_filter_field: str | None = None,
    boundary_filter_value: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Query Lake County stormwater projects in geo_lake_county mode.
    Fetches project attributes from the representative points layer, then fetches actual
    geometries (point, polyline, polygon) in parallel batches using project_id as join key.
    Emits map actions: one layer per geometry type + one layer for representative points.

    IMPORTANT: Before calling this tool for any attribute-based filter, call
    geo_discover_project_schema first to inspect available fields, types, and domain values.
    Build where_clause from what you find in the schema — never assume field names or values.

    Args:
        where_clause: SQL WHERE clause for attribute filtering on the representative points layer.
            Build this from schema discovery. Examples after schema inspection:
            - Filter by a text field: "UPPER(fieldname) LIKE UPPER('%value%')"
            - Numeric comparison: "fieldname > 50000"
            - Exact match: "fieldname = 'value'"
            - Combined: "fieldA = 'X' AND fieldB > 1000"
            Leave as "1=1" to return all projects (subject to project_category filter).
        project_category: Business-logic category — NOT a schema field. Controls which
            project records to include:
            - "projects" (default): excludes flood audits and studies
            - "studies": study projects only
            - "flood_audits": flood audit projects only
        jurisdiction: Municipality/jurisdiction name (e.g. "Village of Antioch"). When provided,
            projects are filtered by jurisdiction AND the municipality boundary is shown on the map.
            Use this for "projects in [municipality]" queries — no need to add jurisdiction to where_clause.
        boundary_layer_id: Layer id of a configured boundary layer to spatially filter projects
            (e.g. "county_board_districts", "drainage_districts", "watersheds"). Use when the
            user asks for projects in a district, watershed, or any boundary.
            Discover the correct filter field from that layer's schema first.
        boundary_filter_field: Field name in the boundary layer (discovered from schema).
        boundary_filter_value: Value to match in boundary_filter_field.
    """
    tid = tool_call_id or ""
    client = _arcgis_client()

    combined_where = _combine_where(project_category, where_clause, jurisdiction)

    spatial_boundary_data = None
    spatial_boundary_label = None

    if boundary_layer_id and boundary_filter_field and boundary_filter_value:
        spatial_boundary_data = await _fetch_layer_boundary(
            boundary_layer_id, boundary_filter_field, boundary_filter_value
        )
        if not spatial_boundary_data or not spatial_boundary_data.get("features"):
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"Could not find boundary '{boundary_filter_value}' "
                                f"in layer '{boundary_layer_id}' using field '{boundary_filter_field}'. "
                                "Please call geo_discover_layer_schema on that layer to verify the correct "
                                "field name and available values, then retry."
                            ),
                            tool_call_id=tid,
                        )
                    ],
                },
            )
        boundary_props = spatial_boundary_data["features"][0].get("properties", {})
        spatial_boundary_label = (
            boundary_props.get(boundary_filter_field) or boundary_filter_value
        )

    rep_query_url = f"{GEO_PROJECT_REPRESENTATIVE_POINTS_URL}/query"

    if spatial_boundary_data and spatial_boundary_data.get("features"):
        boundary_geom = spatial_boundary_data["features"][0].get("geometry")
        esri_polygon = _geojson_geometry_to_esri(boundary_geom) if boundary_geom else None

        if esri_polygon:
            rep_params = {
                "where": combined_where,
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": str(ARCGIS_SRID),
                "f": "geojson",
                "resultRecordCount": str(_MAX_RESULTS),
                "geometry": json.dumps(esri_polygon),
                "geometryType": "esriGeometryPolygon",
                "spatialRel": "esriSpatialRelIntersects",
                "inSR": "4326",
            }
            try:
                rep_data = await client.post(rep_query_url, rep_params, HTTP_TIMEOUT_QUERY)
            except Exception as e:
                logger.error("geo_query_geo_projects_spatial_rep_fetch_failed", error=str(e))
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                content=f"Failed to query projects spatially: {str(e)}",
                                tool_call_id=tid,
                            )
                        ],
                    },
                )
        else:
            rep_params = {
                "where": combined_where,
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
    else:
        rep_params = {
            "where": combined_where,
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

    if spatial_boundary_data and spatial_boundary_data.get("features"):
        map_actions.append({
            "type": "addBoundaryLayer",
            "geojson": spatial_boundary_data,
            "label": f"Boundary: {spatial_boundary_label or boundary_filter_value}",
        })
    elif jurisdiction:
        jurisdiction_boundary = await _fetch_municipality_boundary(jurisdiction)
        if jurisdiction_boundary and jurisdiction_boundary.get("features"):
            boundary_props = jurisdiction_boundary["features"][0].get("properties", {})
            label = boundary_props.get("NAME1") or boundary_props.get("NAME") or jurisdiction
            map_actions.append({
                "type": "addBoundaryLayer",
                "geojson": jurisdiction_boundary,
                "label": f"Jurisdiction: {label}",
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
    if where_clause and where_clause.strip() and where_clause.strip() != "1=1":
        summary_parts.append(f"filter: {where_clause.strip()}")
    if spatial_boundary_label:
        summary_parts.append(f"within {spatial_boundary_label}")
    summary_parts.append(
        f"{with_geom} with actual geometry, {total - with_geom} reference points only"
    )

    _skip = frozenset({"OBJECTID", "GlobalID", "Shape__Area", "Shape__Length", "_color"})
    feature_rows: list[dict] = []
    for feat in rep_features:
        props = feat.get("properties", {})
        row = {k: v for k, v in props.items() if v is not None and str(v).strip() and k not in _skip}
        if row:
            feature_rows.append(row)

    charts_data = _build_charts_from_rows(feature_rows, [])
    geo_result_summary = {
        "total": total,
        "label": "project",
        "label_plural": "projects",
        "feature_rows": feature_rows,
        "charts_data": charts_data,
        "filters": {
            k: v for k, v in {
                "category": project_category,
                "where": where_clause if where_clause and where_clause.strip() != "1=1" else None,
                "boundary": spatial_boundary_label,
            }.items() if v
        },
    }

    return Command(
        update={
            "map_actions": map_actions,
            "geo_result_summary": geo_result_summary,
            "messages": [ToolMessage(content=". ".join(summary_parts), tool_call_id=tid)],
        },
    )


register_tool(geo_query_geo_projects)
