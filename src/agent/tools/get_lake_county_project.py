"""
Tool to search for a Lake County project by name and return geometry + attributes.
"""
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.api.lake_county_service import search_lake_county_project
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _format_attributes(attrs: dict) -> str:
    """Format project attributes for display."""
    lines = []
    for k, v in sorted(attrs.items()):
        if v is not None and str(v).strip():
            label = k.replace("_", " ").title()
            lines.append(f"- **{label}:** {v}")
    return "\n".join(lines) if lines else "No attributes available."


@tool("get_lake_county_project")
async def get_lake_county_project(
    project_name: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Search for a Lake County stormwater project by name and return its geometry and details.
    Use when data_source is Lake County and the user asks about a specific project by name.
    """
    logger.info("GET_LAKE_COUNTY_PROJECT", project_name=project_name)

    result = await search_lake_county_project(project_name)

    if not result["found"] or not result["matches"]:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content=f"No Lake County project found matching '{project_name}'. Try a different name or partial search.",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    matches = result["matches"]

    if len(matches) == 1:
        m = matches[0]
        attrs = m["attributes"] or {}
        geometry = m["geometry"]
        aoi = {"source": "lake_county", "geometry": geometry} if geometry else None
        summary = _format_attributes(attrs)
        tool_message = f"""# Project found: {attrs.get('Name', project_name)}

{summary}

The map will zoom to this project and show the PIN and geometry."""
        return Command(
            update={
                "project_result": {
                    "rep_point_geojson": m.get("rep_point_geojson"),
                    "geometry_geojson": m.get("geometry_geojson"),
                    "geojson": m.get("geometry_geojson") or m.get("rep_point_geojson"),
                    "attributes": attrs,
                },
                "aoi": aoi,
                "aoi_name": attrs.get("Name", project_name),
                "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)],
            },
        )

    names = [m["attributes"].get("Name", "Unknown") for m in matches]
    tool_message = f"""# Found {len(matches)} projects matching "{project_name}"

Select one from the options below to view its details and location on the map:

{chr(10).join(f"- {n}" for n in names)}

Click a project button above the map to view it."""

    return Command(
        update={
            "project_result": {
                "multiple": True,
                "matches": matches,
                "search_term": project_name,
            },
            "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)],
        },
    )
