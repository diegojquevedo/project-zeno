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
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    List Lake County stormwater projects by filters.
    Use when data_source is Lake County and the user asks for projects matching criteria, e.g.:
    - "What projects are Under Review?" -> project_status="Under Review"
    - "Projects with status Submitted" -> status="Submitted"
    - "Projects in jurisdiction Village of Wadsworth" -> jurisdiction="Village of Wadsworth"
    - "Projects where Village of Wadsworth is a project partner" -> project_partners="Village of Wadsworth"
    - "Submitted projects in Village of Wadsworth" -> status="Submitted", jurisdiction="Village of Wadsworth"
    - "Projects with flood areas in Wadsworth" -> project_types=["Capital","WMB","SIRF"], jurisdiction="Village of Wadsworth"

    project_types: use the project type definitions from the prompt to reason. E.g. flood-related -> Capital, WMB, SIRF.
    Valid values are resolved automatically from the data. Pass the user's terms as-is.
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

    jurisdiction_boundary = None
    if jurisdiction_val:
        jurisdiction_boundary = await fetch_municipality_boundary(jurisdiction_val)

    project_types_val = [t.strip() for t in project_types if t and str(t).strip()] if project_types else None

    result = await query_lake_county_projects(
        status=resolved_status,
        project_status=resolved_project_status,
        project_types=project_types_val,
        jurisdiction=jurisdiction_val,
        project_partners=partners_val,
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
        tool_message += "\n\n**Note:** Results are limited to 50. Refine your filters to see a complete list."

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
