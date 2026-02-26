from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.services.lake_county_service import get_soil_types_for_project
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


@tool("get_project_surrounding_soils")
async def get_project_surrounding_soils(
    project_name: str,
    radius_meters: int | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Get soil types (NRCS soil codes) for a Lake County project.
    If radius_meters is provided, returns soils within that distance around the project.
    If not provided, returns soils that touch/intersect the project geometry (point, line, or polygon).
    Use when user asks about soil types for a specific project (e.g. "soil types for project X" or "soils around project Y within 50m").
    """
    logger.info("GET_PROJECT_SURROUNDING_SOILS", project_name=project_name, radius_meters=radius_meters)

    result = await get_soil_types_for_project(project_name, radius_meters=radius_meters)

    if not result.get("found"):
        err = result.get("error", "Project not found")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Could not get soil types: {err}.",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    name = result.get("project_name", project_name)
    codes = result.get("soil_codes", [])
    radius = result.get("radius_meters")

    if not codes:
        scope = f"within {radius}m" if radius is not None else "touching the project"
        update: dict = {
            "messages": [
                ToolMessage(
                    content=f"No soil polygons found {scope} for project **{name}**. The project may be outside NRCS soils coverage or in water/other non-soil area.",
                    tool_call_id=tool_call_id,
                )
            ],
        }
        project_match = result.get("project_match")
        if project_match:
            pr = dict(project_match)
            pr["district_boundary"] = None
            update["project_result"] = pr
        return Command(update=update)

    scope_desc = f"within {radius} meters" if radius is not None else "touching the project geometry"
    soil_list = ", ".join(codes)
    msg = f"# Soil types for project **{name}** ({scope_desc})\n\n**Soil codes:** {soil_list}\n\nTotal: {len(codes)} soil type(s)."

    update = {
        "messages": [
            ToolMessage(
                content=msg,
                tool_call_id=tool_call_id,
            )
        ],
    }
    project_match = result.get("project_match")
    soil_polygons_geojson = result.get("soil_polygons_geojson")
    if project_match:
        pr = dict(project_match)
        pr["district_boundary"] = soil_polygons_geojson
        pr["boundary_type"] = "soil"
        update["project_result"] = pr
    return Command(update=update)
