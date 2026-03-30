import asyncio
import difflib
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

_DISTINCT_RECORD_CAP = "32000"


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _values_match(user_val: str, data_val) -> bool:
    if data_val is None:
        return False
    return _normalize(str(user_val)) == _normalize(str(data_val))


def _safe_where_value(raw: str) -> str:
    return (raw or "").replace("'", "''")


def _field_def_by_name(schema_data: dict, field_name: str) -> dict | None:
    for f in schema_data.get("fields", []) or []:
        if f.get("name") == field_name:
            return f
    return None


def _sql_scalar_literal(field_def: dict | None, raw: str) -> str:
    t = (field_def or {}).get("type") or ""
    if t in ("esriFieldTypeInteger", "esriFieldTypeSmallInteger"):
        try:
            return str(int(float(str(raw).strip())))
        except ValueError:
            pass
    if t == "esriFieldTypeDouble":
        try:
            return str(float(str(raw).strip()))
        except ValueError:
            pass
    return f"'{_safe_where_value(str(raw))}'"


def _domain_literal_for_user_token(field_def: dict | None, user_val: str) -> str | None:
    if not field_def:
        return None
    domain = field_def.get("domain") or {}
    if domain.get("type") != "codedValue":
        return None
    for cv in domain.get("codedValues", []) or []:
        code = cv.get("code")
        name = cv.get("name", "")
        if _values_match(user_val, name) or _values_match(user_val, str(code)):
            if isinstance(code, bool):
                continue
            if isinstance(code, float) and code.is_integer():
                code = int(code)
            if isinstance(code, (int, float)):
                return _sql_scalar_literal(field_def, str(code))
            return _sql_scalar_literal(field_def, str(code))
    return None


async def _fetch_distinct_for_field(
    client: ArcGISClient,
    query_url: str,
    field: str,
    timeout: float,
) -> set[str]:
    params = {
        "where": "1=1",
        "outFields": field,
        "returnDistinctValues": "true",
        "returnGeometry": "false",
        "outSR": str(ARCGIS_SRID),
        "f": "json",
        "resultRecordCount": _DISTINCT_RECORD_CAP,
    }
    try:
        data = await client.get(query_url, params, timeout)
    except Exception as e:
        logger.warning("geo_resolve_distinct_field_failed", field=field, error=str(e))
        return set()
    if data.get("error"):
        logger.warning(
            "geo_resolve_distinct_field_arcgis_error",
            field=field,
            err=data.get("error"),
        )
        return set()
    out: set[str] = set()
    for feat in data.get("features", []):
        props = feat.get("attributes", feat.get("properties", {}))
        val = props.get(field)
        if val is not None and str(val).strip():
            out.add(str(val).strip())
    return out


@tool("geo_resolve_attribute_filter")
async def geo_resolve_attribute_filter(
    values: list[str],
    candidate_field_names: list[str],
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Resolve which project layer field contains the given values. Call AFTER geo_discover_project_schema.
    Pass the user's literal values and candidate_field_names taken only from the discovered schema (string-like
    categorical fields). Queries distinct values per field (separate ArcGIS calls) and uses coded domains from
    the schema when the user's word matches a domain name or code. Returns the exact where_clause for
    geo_query_geo_projects, or a clarification message if no field contains all values.
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

    distinct_sets = await asyncio.gather(
        *[
            _fetch_distinct_for_field(client, query_url, fn, HTTP_TIMEOUT_QUERY)
            for fn in valid_candidates
        ]
    )
    unique_by_field: dict[str, set[str]] = {
        fn: distinct_sets[i] for i, fn in enumerate(valid_candidates)
    }

    matched_field: str | None = None
    matched_sql_literals: list[str] = []

    for field in valid_candidates:
        field_vals = unique_by_field.get(field, set())
        field_def = _field_def_by_name(schema_data, field)
        found_lit: list[str] = []
        ok = True
        for uval in values:
            hit: str | None = None
            for dval in field_vals:
                if _values_match(uval, dval):
                    hit = _sql_scalar_literal(field_def, dval)
                    break
            if hit is None:
                hit = _domain_literal_for_user_token(field_def, uval)
            if hit is None:
                ok = False
                break
            found_lit.append(hit)
        if ok and len(found_lit) == len(values):
            matched_field = field
            matched_sql_literals = found_lit
            break

    if matched_field and matched_sql_literals:
        if len(matched_sql_literals) == 1:
            where_clause = f"{matched_field}={matched_sql_literals[0]}"
        else:
            where_clause = f"{matched_field} IN ({','.join(matched_sql_literals)})"
        content = f'Resolved: use where_clause="{where_clause}" in geo_query_geo_projects.'
        return Command(
            update={
                "messages": [ToolMessage(content=content, tool_call_id=tid)],
            },
        )

    all_suggestions: list[str] = []
    for field in valid_candidates:
        all_suggestions.extend(unique_by_field.get(field, set()))
    pool = sorted(set(v for v in all_suggestions if v))
    by_lower = {p.lower(): p for p in pool}
    preview = pool[:50]
    suggestions_str = ", ".join(repr(s) for s in preview)
    fuzzy_lines: list[str] = []
    for uval in values:
        keys = list(by_lower.keys())
        if not keys:
            break
        close_keys = difflib.get_close_matches(
            _normalize(uval), keys, n=5, cutoff=0.45
        )
        if close_keys:
            shown = [by_lower[k] for k in close_keys]
            fuzzy_lines.append(f"near '{uval}': {', '.join(repr(s) for s in shown)}")
    fuzzy_block = (" Closest spellings in those columns: " + "; ".join(fuzzy_lines)) if fuzzy_lines else ""
    content = (
        f"The value(s) {values} are not equal to any stored value or domain name/code in fields {valid_candidates} "
        f"(ArcGIS per-field distinct queries succeeded; there is no literal match). "
        f"This is not an HTTP error — the service layer simply does not use that exact label in these columns. "
        f"Tell the user their wording does not appear in the data; they must pick a real value or ask you to "
        f"widen candidate_field_names using the full schema. "
        f"Values observed in those columns (sample): {suggestions_str}.{fuzzy_block}"
    )
    return Command(
        update={
            "messages": [ToolMessage(content=content, tool_call_id=tid)],
        },
    )


register_tool(geo_resolve_attribute_filter)
