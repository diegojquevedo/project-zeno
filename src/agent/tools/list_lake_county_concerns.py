"""
Tool to list Lake County concerns (CIRS).
Shows concerns with status_CIRS <> 'Archived'. Optional filters: jurisdiction, category_report, problem, frequency_problem.
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
    query_lake_county_concerns,
)
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _format_concern_summary(matches: list) -> str:
    """Build a short summary of concerns for the tool message using construction_issue and description."""
    if not matches:
        return "No concerns found."
    lines = [f"Found **{len(matches)}** concern(s):"]
    for i, m in enumerate(matches[:15], 1):
        attrs = m.get("attributes", {})
        concern_id = attrs.get("concern_id", "?")
        problem = attrs.get("problem") or "—"
        jurisdiction = attrs.get("jurisdiction") or "—"
        status = attrs.get("status_CIRS") or "—"
        construction_issue = attrs.get("construction_issue") or attrs.get("description") or "—"
        summary_piece = (construction_issue[:80] + "…") if construction_issue and len(str(construction_issue)) > 80 else construction_issue
        lines.append(f"{i}. Concern #{concern_id} — {problem} — {jurisdiction} — {status} — {summary_piece}")
    if len(matches) > 15:
        lines.append(f"... and {len(matches) - 15} more.")
    return "\n".join(lines)


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

    summary = _format_concern_summary(matches)
    filters_applied = []
    if jurisdiction_val:
        filters_applied.append(f"jurisdiction: **{jurisdiction_val}**")
    if category_val:
        filters_applied.append(f"category_report: **{category_val}**")
    if problem_val:
        filters_applied.append(f"problem: **{problem_val}**")
    if frequency_val:
        filters_applied.append(f"frequency_problem: **{frequency_val}**")
    if filters_applied:
        summary += f"\n\nFiltered by {' | '.join(filters_applied)}."
    if limit_exceeded:
        summary += "\n\n**Note:** Results are limited. Refine filters to see a complete list."
    else:
        summary += "\n\nAll concerns are displayed on the map."

    project_result = {
        "list": True,
        "entity_type": "concerns",
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
