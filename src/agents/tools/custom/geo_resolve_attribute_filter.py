from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.agents.custom_tools_registry import register_tool
from src.agents.tools.geo_discover_layer_schema import _fetch_layer_schema
from src.api.custom.geo_lake_county_projects_config import (
    GEO_PROJECT_REPRESENTATIVE_POINTS_URL,
)
from src.api.lake_county_constants import ARCGIS_SRID, HTTP_TIMEOUT_QUERY
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

_SKIP_FIELDS = frozenset({"OBJECTID", "GlobalID", "SHAPE", "Shape__Area", "Shape__Length"})


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _values_match(user_val: str, data_val) -> bool:
    if data_val is None:
        return False
    return _normalize(str(user_val)) == _normalize(str(data_val))


def _safe_where_value(raw: str) -> str:
    return (raw or "").replace("'", "''")


@tool("geo_resolve_attribute_filter")
async def geo_resolve_attribute_filter(
    values: list[str],
    candidate_field_names: list[str],
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Resolve which project layer field contains the given values. Call AFTER geo_discover_project_schema.
    Pass the values the user is looking for (e.g. ["Approved", "Recommended"]) and the candidate field
    names deduced from the schema (e.g. ["status", "ProjectStatus"]). Returns the exact where_clause to
    use in geo_query_geo_projects, or a message asking the user to clarify if values are not found.
    """
    tid = tool_call_id or ""
    if not values or not candidate_field_names:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Both values and candidate_field_names must be non-empty.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    schema_data = await _fetch_layer_schema(GEO_PROJECT_REPRESENTATIVE_POINTS_URL)
    if not schema_data:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Failed to fetch project layer schema from ArcGIS.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    schema_field_names = {f.get("name") for f in schema_data.get("fields", []) if f.get("name")}
    valid_candidates = [f for f in candidate_field_names if f in schema_field_names and f not in _SKIP_FIELDS]
    if not valid_candidates:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"None of the candidate fields ({candidate_field_names}) exist in the project schema.",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    client = ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_QUERY)
    query_url = f"{GEO_PROJECT_REPRESENTATIVE_POINTS_URL}/query"
    params = {
        "where": "1=1",
        "outFields": ",".join(valid_candidates),
        "returnDistinctValues": "true",
        "returnGeometry": "false",
        "outSR": str(ARCGIS_SRID),
        "f": "json",
        "resultRecordCount": 10000,
    }
    try:
        data = await client.get(query_url, params, HTTP_TIMEOUT_QUERY)
    except Exception as e:
        logger.warning("geo_resolve_attribute_filter_query_failed", error=str(e))
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to query distinct values from ArcGIS: {e}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    if data.get("error"):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"ArcGIS error: {data['error'].get('message', 'Unknown error')}",
                        tool_call_id=tid,
                    )
                ],
            },
        )

    unique_by_field: dict[str, set[str]] = {f: set() for f in valid_candidates}
    for feat in data.get("features", []):
        props = feat.get("attributes", feat.get("properties", {}))
        for field in valid_candidates:
            val = props.get(field)
            if val is not None and str(val).strip():
                unique_by_field[field].add(str(val))

    matched_field: str | None = None
    matched_values: list[str] = []

    for field in valid_candidates:
        field_vals = unique_by_field.get(field, set())
        found = []
        for uval in values:
            for dval in field_vals:
                if _values_match(uval, dval):
                    found.append(dval)
                    break
        if len(found) == len(values):
            matched_field = field
            matched_values = found
            break

    if matched_field and matched_values:
        escaped = [f"'{_safe_where_value(v)}'" for v in matched_values]
        if len(escaped) == 1:
            where_clause = f"{matched_field}={escaped[0]}"
        else:
            where_clause = f"{matched_field} IN ({','.join(escaped)})"
        content = f'Resolved: use where_clause="{where_clause}" in geo_query_geo_projects.'
        return Command(
            update={
                "messages": [ToolMessage(content=content, tool_call_id=tid)],
            },
        )

    all_suggestions: list[str] = []
    for field in valid_candidates:
        all_suggestions.extend(unique_by_field.get(field, set()))
    unique_suggestions = sorted(set(v for v in all_suggestions if v))[:20]
    suggestions_str = ", ".join(repr(s) for s in unique_suggestions)
    content = (
        f"The value(s) {values} were not found in any of the candidate fields ({valid_candidates}). "
        "Please ask the user to clarify what they mean. "
        f"Available values in those fields: {suggestions_str}"
    )
    return Command(
        update={
            "messages": [ToolMessage(content=content, tool_call_id=tid)],
        },
    )


register_tool(geo_resolve_attribute_filter)
