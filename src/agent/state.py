from typing import Annotated, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict

from src.agent.tools.code_executors.base import CodeActPart


def add_aois(left, right):
    """Merges two AOIs and returns the merged AOI (legacy; prefer replace_aoi_options)."""
    if not isinstance(left, list):
        left = [left]
    if not isinstance(right, list):
        right = [right]
    return left + right


def replace_aoi_options(left, right):
    """Replace aoi_options with the new selection so each query uses only the current AOI(s)."""
    if right is None:
        return left
    return [right] if not isinstance(right, list) else right


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_persona: str
    data_source: str  # "forest_carbon" | "lake_county"

    # pick-aoi tool
    aoi: dict
    subregion_aois: dict
    subregion: str
    aoi_name: str
    subtype: str
    aoi_options: Annotated[list[dict], replace_aoi_options]

    # pick-dataset tool
    dataset: dict

    # Lake County project lookup
    project_result: dict

    # pull-data tool
    raw_data: dict
    start_date: str
    end_date: str

    # generate-insights tool
    insights: list
    charts_data: list
    codeact_parts: list[CodeActPart]
