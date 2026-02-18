"""
Tool to list Lake County projects by filters (status, jurisdiction, project partners, etc.).
Uses domains to resolve user terms to actual field values.
"""
from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agent.tools.lake_county_project_summary import build_project_summary_and_chart
from src.api.lake_county_config import (
    PROJECT_CATEGORY_FLOOD_AUDITS,
    PROJECT_CATEGORY_PROJECTS,
    PROJECT_CATEGORY_STUDIES,
)
from src.api.lake_county_service import (
    fetch_lake_county_domains,
    fetch_municipality_boundary,
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
    project_partners: str | None = None,
    subshed: str | None = None,
    project_category: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    List Lake County stormwater projects by filters.
    Use when data_source is Lake County and the user asks for projects matching criteria.

    project_category (IMPORTANT - matches INFLOW tabs):
    - "projects": Normal projects only, EXCLUDES Flood Audit and Study (default when user asks "projects in Lake County")
    - "studies": Studies only (is_study=1 or projectsubtype=Study)
    - "flood_audits": Flood Audit projects only

    Examples:
    - "Show me projects in Lake County" -> project_category="projects"
    - "Studies in Lake County" -> project_category="studies"
    - "Flood audit projects" -> project_category="flood_audits"
    - "Projects Under Review in Wadsworth" -> project_category="projects", project_status="Under Review", jurisdiction="Wadsworth"
    - "Projects with sub-watershed in Lake Michigan" -> subshed="Lake Michigan"

    project_types: filter by projecttype (Capital, WMB, SIRF, etc.). subshed: filter by sub-watershed.
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
    partners_val = project_partners.strip() if project_partners and str(project_partners).strip() else None
    subshed_val = subshed.strip() if subshed and str(subshed).strip() else None

    jurisdiction_boundary = None
    if jurisdiction_val:
        jurisdiction_boundary = await fetch_municipality_boundary(jurisdiction_val)

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

    # If no filters, default to "projects" (exclude Flood Audit and Study) for "projects in Lake County"
    has_filters = any([
        resolved_status,
        resolved_project_status,
        project_types_val,
        jurisdiction_val,
        partners_val,
        subshed_val,
    ])
    if not has_filters and not category_val:
        category_val = PROJECT_CATEGORY_PROJECTS  # Default: normal projects only

    result = await query_lake_county_projects(
        status=resolved_status,
        project_status=resolved_project_status,
        project_types=project_types_val,
        jurisdiction=jurisdiction_val,
        project_partners=partners_val,
        subshed=subshed_val,
        project_category=category_val,
        allow_no_filters=not has_filters and not category_val,
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

    update = {
        "project_result": project_result,
        "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)],
    }
    if charts_data:
        update["charts_data"] = charts_data

    return Command(update=update)
