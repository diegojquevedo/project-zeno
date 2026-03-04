from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.agents.custom_tools_registry import register_tool
from src.agents.tools.geo_discover_layer_schema import _fetch_layer_schema, _format_schema_summary
from src.api.custom.geo_lake_county_projects_config import GEO_PROJECT_REPRESENTATIVE_POINTS_URL
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


@tool("geo_discover_project_schema")
async def geo_discover_project_schema(
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Fetch the schema (fields, types, domains) of the projects representative points layer.
    Call this before building any where_clause for geo_query_geo_projects.
    Returns all available fields with their types, aliases, and domain values so you can
    construct correct SQL filters without assuming any field names or values.
    """
    tid = tool_call_id or ""
    data = await _fetch_layer_schema(GEO_PROJECT_REPRESENTATIVE_POINTS_URL)
    if not data:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Failed to fetch project layer schema from ArcGIS.",
                        tool_call_id=tid,
                    )
                ],
            },
        )
    summary = _format_schema_summary(data)
    return Command(
        update={
            "messages": [ToolMessage(content=summary, tool_call_id=tid)],
        },
    )


register_tool(geo_discover_project_schema)
