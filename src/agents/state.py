from typing import Annotated, Any, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict

from src.agents.schemas import CodeActPart


def add_aois(left: list[dict[str, Any]] | Any, right: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Merges two AOIs and returns the merged AOI (legacy; prefer replace_aoi_options)."""
    if not isinstance(left, list):
        left = [left]
    if not isinstance(right, list):
        right = [right]
    return left + right


def add_map_actions(left: list[dict[str, Any]] | Any, right: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Append new map actions to existing ones."""
    if not isinstance(left, list):
        left = [] if left is None else [left]
    if not isinstance(right, list):
        right = [] if right is None else [right]
    return left + right


def replace_aoi_options(left: list[dict[str, Any]], right: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Replace aoi_options with the new selection so each query uses only the current AOI(s)."""
    if right is None:
        return left
    return [right] if not isinstance(right, list) else right


class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_persona: str
    data_source: str

    # pick-aoi tool
    aoi: dict[str, Any]
    subregion_aois: list[dict[str, Any]]
    subregion: str
    aoi_name: str
    subtype: str
    aoi_options: Annotated[list[dict[str, Any]], replace_aoi_options]

    # pick-dataset tool
    dataset: dict[str, Any]

    # Lake County project lookup
    project_result: dict[str, Any] | None

    geo_query_result: dict[str, Any] | None
    geo_boundary_result: dict[str, Any] | None
    geo_spatial_intersection_result: dict[str, Any] | None
    geo_result_summary: dict[str, Any] | None
    geo_project_geometry: dict[str, Any] | None

    map_actions: Annotated[list[dict[str, Any]], add_map_actions]

    raw_data: dict[str, Any]
    start_date: str
    end_date: str

    # generate-insights tool
    insights: list[Any]
    charts_data: list[dict[str, Any]]
    codeact_parts: list[CodeActPart]
