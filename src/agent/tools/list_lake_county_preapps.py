"""
Tool to list Lake County pre-applications (PreApps).
Shows preapps with status <> 'Archived'. Optional jurisdiction and subshed filters.
"""
from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agent.tools.lake_county_project_summary import build_preapp_summary_and_chart
from src.api.lake_county_config import JURISDICTION_ALIASES
from src.api.lake_county_service import (
    fetch_municipality_boundary,
    query_lake_county_preapps,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _last_user_message(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content = getattr(m, "content", None)
            return str(content).strip() if content else ""
    return ""


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

    user_query = _last_user_message((state or {}).get("messages", []))
    tool_message, charts_data = await build_preapp_summary_and_chart(matches, user_query)

    if limit_exceeded:
        tool_message += "\n\n**Note:** Results are limited. Refine jurisdiction or sub-watershed to see a complete list."

    project_result = {
        "list": True,
        "entity_type": "preapps",
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
