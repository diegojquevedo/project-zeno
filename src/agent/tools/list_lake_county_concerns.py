"""
Tool to list Lake County concerns (CIRS).
Shows concerns with status_CIRS <> 'Archived'. Optional filters: jurisdiction, category_report, problem, frequency_problem.
"""
from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agent.tools.lake_county_project_summary import build_concern_summary_and_chart
from src.api.lake_county_config import JURISDICTION_ALIASES
from src.api.lake_county_service import (
    fetch_municipality_boundary,
    query_lake_county_concerns,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _last_user_message(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content = getattr(m, "content", None)
            return str(content).strip() if content else ""
    return ""


@tool("list_lake_county_concerns")
async def list_lake_county_concerns(
    jurisdiction: str | None = None,
    category_report: str | None = None,
    problem: str | None = None,
    frequency_problem: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    List Lake County concerns (CIRS).
    Use when data_source is Lake County and the user asks for concerns, CIRS, or reported issues.

    Always excludes Archived concerns. Optional filters:
    - jurisdiction: municipality (e.g. "North Chicago", "Zion").
    - category_report: e.g. "Major", "Minor".
    - problem: e.g. "Construction", "Floodplain / Flooding".
    - frequency_problem: e.g. "Annually", "First Time".

    Examples:
    - "Show me concerns in Lake County" or "all concerns in LC" -> no filters (all non-Archived)
    - "Concerns in Chicago" or "Concerns in North Chicago" -> jurisdiction="Chicago" (maps to North Chicago)
    - "Concerns with problem Construction" -> problem="Construction"
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

    category_val = category_report.strip() if category_report and str(category_report).strip() else None
    problem_val = problem.strip() if problem and str(problem).strip() else None
    frequency_val = frequency_problem.strip() if frequency_problem and str(frequency_problem).strip() else None

    result = await query_lake_county_concerns(
        jurisdiction=jurisdiction_val,
        category_report=category_val,
        problem=problem_val,
        frequency_problem=frequency_val,
    )

    if not result["found"]:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content="No concerns found in Lake County matching the criteria. Try different filters (jurisdiction, category_report, problem, frequency_problem).",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    matches = result["matches"]
    limit_exceeded = result.get("limit_exceeded", False)

    user_query = _last_user_message((state or {}).get("messages", []))
    tool_message, charts_data = await build_concern_summary_and_chart(matches, user_query)

    if limit_exceeded:
        tool_message += "\n\n**Note:** Results are limited. Refine filters to see a complete list."

    project_result = {
        "list": True,
        "entity_type": "concerns",
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
