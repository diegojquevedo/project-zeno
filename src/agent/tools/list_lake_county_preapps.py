"""
Tool to list Lake County pre-applications (PreApps).
Shows preapps with status <> 'Archived'. Optional jurisdiction and subshed filters.
"""
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.api.lake_county_config import JURISDICTION_ALIASES
from src.api.lake_county_service import (
    fetch_municipality_boundary,
    query_lake_county_preapps,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _format_preapp_summary(matches: list) -> str:
    """Build a short summary of preapps for the tool message."""
    if not matches:
        return "No pre-applications found."
    lines = [f"Found **{len(matches)}** pre-application(s):"]
    for i, m in enumerate(matches[:15], 1):
        attrs = m.get("attributes", {})
        name = attrs.get("Name") or attrs.get("Address") or f"PreApp #{attrs.get('preapp_id', '?')}"
        jurisdiction = attrs.get("jurisdiction") or "—"
        subshed_val = attrs.get("Subshed") or "—"
        status_val = attrs.get("status") or "—"
        lines.append(f"{i}. {name} — {jurisdiction} — {subshed_val} — {status_val}")
    if len(matches) > 15:
        lines.append(f"... and {len(matches) - 15} more.")
    return "\n".join(lines)


@tool("list_lake_county_preapps")
async def list_lake_county_preapps(
    jurisdiction: str | None = None,
    subshed: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    List Lake County pre-applications (PreApps).
    Use when data_source is Lake County and the user asks for preapps.

    - jurisdiction: filter by municipality (e.g. "North Chicago", "Zion").
    - subshed: filter by sub-watershed (e.g. "Lake Michigan", "North Branch Chicago River").

    Examples:
    - "Show me preapps in Lake County" -> no filters
    - "Preapps in Chicago" or "Preapps in North Chicago" -> jurisdiction="Chicago" (maps to North Chicago)
    - "Preapps with sub-watershed in Lake Michigan" or "preapps in Lake Michigan subshed" -> subshed="Lake Michigan"
    """
    raw_jurisdiction = jurisdiction.strip() if jurisdiction and str(jurisdiction).strip() else None
    jurisdiction_val = (
        JURISDICTION_ALIASES.get(raw_jurisdiction.lower(), raw_jurisdiction)
        if raw_jurisdiction
        else None
    )

    jurisdiction_boundary = None
    if jurisdiction_val:
        jurisdiction_boundary = await fetch_municipality_boundary(jurisdiction_val)

    subshed_val = subshed.strip() if subshed and str(subshed).strip() else None

    result = await query_lake_county_preapps(
        jurisdiction=jurisdiction_val,
        subshed=subshed_val,
    )

    if not result["found"]:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content="No pre-applications found in Lake County matching the criteria. Try a different jurisdiction, sub-watershed, or check filters.",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    matches = result["matches"]
    limit_exceeded = result.get("limit_exceeded", False)

    summary = _format_preapp_summary(matches)
    filters_applied = []
    if jurisdiction_val:
        filters_applied.append(f"jurisdiction: **{jurisdiction_val}**")
    if subshed_val:
        filters_applied.append(f"sub-watershed: **{subshed_val}**")
    if filters_applied:
        summary += f"\n\nFiltered by {' | '.join(filters_applied)}."
    if limit_exceeded:
        summary += "\n\n**Note:** Results are limited. Refine jurisdiction to see a complete list."
    else:
        summary += "\n\nAll pre-applications are displayed on the map."

    project_result = {
        "list": True,
        "entity_type": "preapps",
        "matches": matches,
        "total_returned": len(matches),
        "limit_exceeded": limit_exceeded,
    }
    if jurisdiction_boundary and jurisdiction_boundary.get("features"):
        project_result["jurisdiction_boundary"] = jurisdiction_boundary

    return Command(
        update={
            "project_result": project_result,
            "messages": [ToolMessage(content=summary, tool_call_id=tool_call_id)],
        },
    )
