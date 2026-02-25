import json
from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agents.tools.lake_county_project_summary import (
    build_project_summary_and_chart,
)
from src.api.lake_county_config import (
    PROJECT_CATEGORY_FLOOD_AUDITS,
    PROJECT_CATEGORY_PROJECTS,
    PROJECT_CATEGORY_STUDIES,
)
from src.services.lake_county_service import (
    buffer_point_km,
    district_geometry_to_esri,
    fetch_county_board_district_boundary,
    fetch_drainage_district_boundary,
    fetch_lake_county_domains,
    fetch_municipality_boundary,
    fetch_state_representative_district_boundary,
    fetch_state_senate_district_boundary,
    fetch_us_congressional_district_boundary,
    get_place_center,
    query_lake_county_projects,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _resolve_value(user_value: str, domain_values: list[str]) -> str | None:
    """Case-insensitive match; prefer exact, then startswith, then contains."""
    if not user_value or not domain_values:
        return None
    uv = user_value.strip().lower()
    for d in domain_values:
        if d.lower() == uv:
            return d
    for d in domain_values:
        if d.lower().startswith(uv) or uv in d.lower():
            return d
    return None


def _format_attributes(attrs: dict) -> str:
    """Format project attributes for display."""
    lines = []
    for k, v in sorted(attrs.items()):
        if v is not None and str(v).strip():
            label = k.replace("_", " ").title()
            lines.append(f"- **{label}:** {v}")
    return "\n".join(lines) if lines else "No attributes available."


def _last_user_message(messages: list) -> str:
    """Extract content from last HumanMessage in conversation."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content = getattr(m, "content", None)
            return str(content).strip() if content else ""
    return ""


@tool("list_lake_county_projects")
async def list_lake_county_projects(
    status: str | None = None,
    project_status: str | None = None,
    project_types: list[str] | None = None,
    jurisdiction: str | None = None,
    county_board_district: str | None = None,
    drainage_district: str | None = None,
    state_senate_district: str | None = None,
    state_representative_district: str | None = None,
    us_congressional_district: str | None = None,
    project_partners: str | None = None,
    subshed: str | None = None,
    project_category: str | None = None,
    place_name: str | None = None,
    radius_km: float | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    List Lake County stormwater projects by filters.
    Use when data_source is Lake County and the user asks for projects matching criteria.

    For "projects within X km of [place]" or "projects near [place]": use place_name and radius_km.
    place_name: municipality or place in Lake County (e.g. Gurnee, Waukegan). radius_km: distance in kilometers (e.g. 5).
    If user says miles, convert: 5 miles ≈ 8 km.

    project_category (IMPORTANT - matches INFLOW tabs):
    - "projects": Normal projects only, EXCLUDES Flood Audit and Study (default when user asks "projects in Lake County")
    - "studies": Studies only (is_study=1 or projectsubtype=Study)
    - "flood_audits": Flood Audit projects only

    Examples:
    - "Show me projects in Lake County" -> project_category="projects"
    - "Studies in Lake County" -> project_category="studies"
    - "Flood audit projects" -> project_category="flood_audits"
    - "Projects Under Review in Wadsworth" -> project_category="projects", project_status="Under Review", jurisdiction="Wadsworth"
    - "Projects in county board district 5" -> project_category="projects", county_board_district="5"
    - "Projects in drainage district Union No 1" -> drainage_district="Union No 1"
    - "Projects in state senate district 31" -> state_senate_district="31"
    - "Projects in state rep district 59" -> state_representative_district="59"
    - "Projects in US congressional district 10" -> us_congressional_district="10"
    - "Projects with sub-watershed in Lake Michigan" -> subshed="Lake Michigan"
    - "Show me projects 5 km from Gurnee" -> place_name="Gurnee", radius_km=5
    - "Projects within 10 miles of Waukegan" -> place_name="Waukegan", radius_km=16

    project_types: filter by projecttype (Capital, WMB, SIRF, etc.). subshed: filter by sub-watershed.
    county_board_district: filter by County Board District (number or name).
    drainage_district: filter by Drainage District (CODE or NAME).
    state_senate_district: filter by State Senate District (number or name).
    state_representative_district: filter by State Representative District (number or name).
    us_congressional_district: filter by U.S. Congressional District (number or name).
    """
    domains = await fetch_lake_county_domains()

    resolved_status = None
    if status and str(status).strip():
        resolved = _resolve_value(str(status).strip(), domains.get("status", []))
        if resolved:
            resolved_status = resolved
        else:
            resolved_status = str(status).strip()

    resolved_project_status = None
    if project_status and str(project_status).strip():
        resolved = _resolve_value(
            str(project_status).strip(), domains.get("ProjectStatus", [])
        )
        if resolved:
            resolved_project_status = resolved
        else:
            resolved_project_status = str(project_status).strip()

    jurisdiction_val = jurisdiction.strip() if jurisdiction and str(jurisdiction).strip() else None
    county_board_district_val = county_board_district.strip() if county_board_district and str(county_board_district).strip() else None
    drainage_district_val = drainage_district.strip() if drainage_district and str(drainage_district).strip() else None
    state_senate_district_val = state_senate_district.strip() if state_senate_district and str(state_senate_district).strip() else None
    state_rep_district_val = state_representative_district.strip() if state_representative_district and str(state_representative_district).strip() else None
    us_cong_district_val = us_congressional_district.strip() if us_congressional_district and str(us_congressional_district).strip() else None
    partners_val = project_partners.strip() if project_partners and str(project_partners).strip() else None
    subshed_val = subshed.strip() if subshed and str(subshed).strip() else None

    jurisdiction_boundary = None
    if jurisdiction_val:
        jurisdiction_boundary = await fetch_municipality_boundary(jurisdiction_val)

    place_name_val = place_name.strip() if place_name and str(place_name).strip() else None
    radius_km_val = float(radius_km) if radius_km is not None else None
    if radius_km_val is not None and (radius_km_val <= 0 or radius_km_val > 200):
        radius_km_val = None

    district_boundary_geojson = None
    district_geometry = None
    if place_name_val and radius_km_val is not None:
        center = await get_place_center(place_name_val)
        if center:
            lon, lat = center
            buffer_poly = buffer_point_km(lon, lat, radius_km_val)
            if buffer_poly:
                district_geometry = buffer_poly
                district_boundary_geojson = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": buffer_poly,
                            "properties": {"place": place_name_val, "radius_km": radius_km_val},
                        }
                    ],
                }
        if not district_geometry:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Could not find place '{place_name_val}' in Lake County or could not create the radius. Try a municipality name (e.g. Gurnee, Waukegan).",
                            tool_call_id=tool_call_id,
                        )
                    ],
                },
            )
    elif county_board_district_val:
        district_boundary_geojson = await fetch_county_board_district_boundary(county_board_district_val)
    elif drainage_district_val:
        drainage_result = await fetch_drainage_district_boundary(drainage_district_val)
        if drainage_result:
            district_boundary_geojson = drainage_result.get("geojson") or drainage_result
            if drainage_result.get("esri_geometry"):
                district_geometry = drainage_result.get("esri_geometry")
    elif state_senate_district_val:
        district_boundary_geojson = await fetch_state_senate_district_boundary(state_senate_district_val)
    elif state_rep_district_val:
        district_boundary_geojson = await fetch_state_representative_district_boundary(state_rep_district_val)
    elif us_cong_district_val:
        district_boundary_geojson = await fetch_us_congressional_district_boundary(us_cong_district_val)
    if district_boundary_geojson and district_boundary_geojson.get("features") and not district_geometry:
        # Use first feature that has a geometry convertible to Esri (in case first feature has null/different format)
        for feat in district_boundary_geojson["features"]:
            g = feat.get("geometry")
            if g is None and feat.get("geom") is not None:
                g = feat.get("geom")
            if isinstance(g, str):
                try:
                    g = json.loads(g)
                except Exception:
                    g = None
            if g and isinstance(g, dict) and district_geometry_to_esri(g):
                district_geometry = g
                break
    county_board_district_boundary = district_boundary_geojson if county_board_district_val else None

    project_types_val = [t.strip() for t in project_types if t and str(t).strip()] if project_types else None

    # Resolve project_category: "projects" | "studies" | "flood_audits"
    category_val = None
    if project_category and str(project_category).strip():
        pc = str(project_category).strip().lower()
        if pc in (PROJECT_CATEGORY_PROJECTS, "project"):
            category_val = PROJECT_CATEGORY_PROJECTS
        elif pc in (PROJECT_CATEGORY_STUDIES, "study"):
            category_val = PROJECT_CATEGORY_STUDIES
        elif pc in (PROJECT_CATEGORY_FLOOD_AUDITS, "flood_audit", "flood audit"):
            category_val = PROJECT_CATEGORY_FLOOD_AUDITS

    has_filters = any([
        resolved_status,
        resolved_project_status,
        project_types_val,
        jurisdiction_val,
        county_board_district_val,
        drainage_district_val,
        state_senate_district_val,
        state_rep_district_val,
        us_cong_district_val,
        partners_val,
        subshed_val,
        bool(place_name_val and radius_km_val is not None),
    ])
    if not has_filters and not category_val:
        category_val = PROJECT_CATEGORY_PROJECTS
    if (county_board_district_val or drainage_district_val or state_senate_district_val or state_rep_district_val or us_cong_district_val or (place_name_val and radius_km_val is not None)) and not category_val:
        category_val = PROJECT_CATEGORY_PROJECTS

    result = await query_lake_county_projects(
        status=resolved_status,
        project_status=resolved_project_status,
        project_types=project_types_val,
        jurisdiction=jurisdiction_val,
        project_partners=partners_val,
        subshed=subshed_val,
        project_category=category_val,
        county_board_district_geometry=district_geometry,
        allow_no_filters=not has_filters and not category_val and not district_geometry,
    )

    if not result["found"]:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content="No Lake County projects found matching the filters. Try different criteria or be less specific.",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    matches = result["matches"]
    limit_exceeded = result.get("limit_exceeded", False)

    user_query = _last_user_message((state or {}).get("messages", []))
    tool_message, charts_data = await build_project_summary_and_chart(matches, user_query)

    if limit_exceeded:
        max_shown = 200 if not has_filters else 50
        tool_message += f"\n\n**Note:** Results are limited to {max_shown}. Refine your filters to see a complete list."
    elif not has_filters:
        tool_message += f"\n\n**Note:** Showing all {len(matches)} Lake County projects. All projects are displayed on the map."

    project_result = {
        "list": True,
        "matches": matches,
        "total_returned": len(matches),
        "limit_exceeded": limit_exceeded,
    }
    if jurisdiction_boundary and jurisdiction_boundary.get("features"):
        project_result["jurisdiction_boundary"] = jurisdiction_boundary
    if district_boundary_geojson and district_boundary_geojson.get("features"):
        project_result["district_boundary"] = district_boundary_geojson
    if county_board_district_boundary and county_board_district_boundary.get("features"):
        project_result["county_board_district_boundary"] = county_board_district_boundary

    update = {
        "project_result": project_result,
        "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)],
    }
    if charts_data:
        update["charts_data"] = charts_data

    return Command(update=update)
