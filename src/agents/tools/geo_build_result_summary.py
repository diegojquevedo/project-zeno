from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agents.state import AgentState
from src.agents.tools.geo_narrative_enrichment import compute_narrative_enrichment
from src.api.geo_lake_county_config import get_geo_lake_county_layer_by_id

_SKIP_FIELDS = frozenset({"OBJECTID", "GlobalID", "Shape__Area", "Shape__Length", "_color"})
_MAX_CATEGORY_VALUES = 45
_MIN_CATEGORY_VALUES = 1
_MAX_CHARTS = 3
_EPOCH_MS_THRESHOLD = 253402300800000


def _field_priority_score(field_name: str, unique_count: int) -> float:
    name_lower = field_name.lower()
    score = 0.0
    priority_keywords = ["type", "class", "category", "status", "kind", "code", "group", "zone", "use", "subtype"]
    for kw in priority_keywords:
        if kw in name_lower:
            score += 10.0
            break
    if 2 <= unique_count <= 8:
        score += 5.0
    elif 9 <= unique_count <= 15:
        score += 2.0
    return score


def _build_charts_from_rows(feature_rows: list[dict], requested_fields: list[str]) -> list[dict]:
    if not feature_rows:
        return []

    all_fields: set[str] = set()
    for row in feature_rows:
        all_fields.update(row.keys())
    all_fields -= _SKIP_FIELDS

    field_values: dict[str, list] = {f: [] for f in all_fields}
    for row in feature_rows:
        for field in all_fields:
            field_values[field].append(row.get(field))

    candidate_fields: list[tuple[float, str, dict]] = []

    for field in all_fields:
        values = field_values[field]
        non_null = [v for v in values if v is not None and str(v).strip()]
        if not non_null:
            continue

        numeric_vals = []
        for v in non_null:
            try:
                numeric_vals.append(float(v))
            except (TypeError, ValueError):
                pass
        if numeric_vals and len(numeric_vals) == len(non_null):
            if all(abs(n) > _EPOCH_MS_THRESHOLD for n in numeric_vals if n != 0):
                continue
            if all(n != int(n) or abs(n) > 1e12 for n in numeric_vals):
                continue

        unique_vals = {str(v) for v in non_null}
        unique_count = len(unique_vals)
        if not (_MIN_CATEGORY_VALUES <= unique_count <= _MAX_CATEGORY_VALUES):
            continue

        score = _field_priority_score(field, unique_count)
        if requested_fields:
            field_lower = field.lower()
            for rf in requested_fields:
                if rf.lower() in field_lower or field_lower in rf.lower():
                    score += 20.0

        counts: dict[str, int] = {}
        for v in non_null:
            key = str(v)
            counts[key] = counts.get(key, 0) + 1

        sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
        insight = "Distribution: " + ", ".join(f"{v} {k}" for k, v in sorted_counts[:5])

        candidate_fields.append((score, field, {
            "id": f"chart_{field.lower()}",
            "title": f"By {field.replace('_', ' ').title()}",
            "type": "bar",
            "insight": insight,
            "data": [{"category": k, "count": v} for k, v in sorted_counts],
            "xAxis": "category",
            "yAxis": "count",
            "colorField": "",
            "stackField": "",
            "groupField": "",
            "seriesFields": [],
        }))

    candidate_fields.sort(key=lambda x: -x[0])

    seen_titles: set[str] = set()
    charts: list[dict] = []
    for _, _, chart in candidate_fields:
        if chart["title"] not in seen_titles:
            seen_titles.add(chart["title"])
            charts.append(chart)
        if len(charts) >= _MAX_CHARTS:
            break

    return charts


def _extract_feature_rows(geojson: dict) -> list[dict]:
    rows = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {}) if isinstance(feat, dict) else {}
        cleaned = {k: v for k, v in props.items() if k not in _SKIP_FIELDS and v is not None and str(v).strip()}
        if cleaned:
            rows.append(cleaned)
    return rows


@tool("geo_build_result_summary")
async def geo_build_result_summary(
    source: str,
    result_label: str,
    chart_fields: list[str],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Build a result summary with auto-selected charts from the most recent query result.

    Call this ONLY after geo_query_layer or geo_spatial_intersection returns multiple features.
    Do NOT call after geo_query_geo_projects — that tool builds its own summary with charts.

    Args:
        source: Which state result to read features from. Use:
                "geo_query_result" — after geo_query_layer
                "geo_spatial_intersection_result" — after geo_spatial_intersection
        result_label: Human-readable name for the features (e.g. "soil types",
                      "streams", "municipalities"). Used as the UI header label.
        chart_fields: List of 2-4 field names from schema discovery that are most
                      relevant to chart (categorical fields like type, class, zone,
                      status, code). Pass [] to let the tool decide automatically.
    """
    tid = tool_call_id

    geojson: dict = {}
    layer_id_for_schema: str | None = None
    if source == "geo_query_result":
        result = state.get("geo_query_result") or {}
        geojson = result.get("geojson", {})
        layer_id_for_schema = result.get("layer_id")
    elif source == "geo_spatial_intersection_result":
        result = state.get("geo_spatial_intersection_result") or {}
        geojson = result.get("what_geojson", {})
        layer_id_for_schema = result.get("what_layer_id")

    feature_rows = _extract_feature_rows(geojson)
    total = len(feature_rows)
    charts_data = _build_charts_from_rows(feature_rows, chart_fields or [])

    label_plural = result_label if result_label.endswith("s") else result_label + "s"

    layer_url: str | None = None
    if layer_id_for_schema and layer_id_for_schema != "geo_project_geometry":
        layer_cfg = get_geo_lake_county_layer_by_id(layer_id_for_schema)
        if layer_cfg:
            layer_url = layer_cfg.get("arcgis_url")

    narrative_enrichment = await compute_narrative_enrichment(
        feature_rows,
        layer_url,
        total=total,
        result_label=result_label,
    )

    geo_result_summary = {
        "total": total,
        "label": result_label,
        "label_plural": label_plural,
        "feature_rows": feature_rows,
        "charts_data": charts_data,
        "filters": {},
    }
    if narrative_enrichment:
        geo_result_summary["narrative_enrichment"] = narrative_enrichment

    chart_count = len(charts_data)
    summary = (
        f"Built summary for {total} {label_plural}. "
        f"Generated {chart_count} chart{'s' if chart_count != 1 else ''}"
        + (f": {', '.join(c['title'] for c in charts_data)}." if charts_data else ".")
    )
    if narrative_enrichment:
        summary += " Added rich context from descriptive attribute text (see structured panel)."

    return Command(
        update={
            "geo_result_summary": geo_result_summary,
            "messages": [ToolMessage(content=summary, tool_call_id=tid)],
        },
    )
