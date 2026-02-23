from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class PartType(Enum):
    TEXT_OUTPUT = "text_output"
    CODE_BLOCK = "code_block"
    EXECUTION_OUTPUT = "execution_output"


class CodeActPart(BaseModel):
    type: PartType
    content: str


class DataPullResult(BaseModel):
    success: bool
    data: Any
    message: str
    data_points_count: int = 0
    analytics_api_url: Optional[str] = None


class BooleanResponse(BaseModel):
    result: bool


class AOIIndex(BaseModel):
    source: str = Field(description="`source` of the best matched location.")
    src_id: str = Field(description="`src_id` of the best matched location.")
    name: str = Field(description="`name` of the best matched location.")
    subtype: str = Field(description="`subtype` of the best matched location.")


class Place(BaseModel):
    name: str


class ChartInsight(BaseModel):
    title: str = Field(description="Clear, descriptive title for the chart")
    chart_type: str = Field(
        description="Chart type: 'line', 'bar', 'stacked-bar', 'grouped-bar', 'pie', 'area', 'scatter', or 'table'"
    )
    insight: str = Field(
        description="Key insight or finding that this chart reveals (2-3 sentences)"
    )
    x_axis: str = Field(
        description="Name of the field to use for X-axis (for applicable chart types)"
    )
    y_axis: str = Field(
        description="Name of the field to use for Y-axis (for applicable chart types)"
    )
    color_field: str = Field(
        default="",
        description="Optional field name for color grouping/categorization",
    )
    stack_field: str = Field(
        default="",
        description="Field name for stacking data (for stacked-bar charts)",
    )
    group_field: str = Field(
        default="",
        description="Field name for grouping bars (for grouped-bar charts)",
    )
    series_fields: List[str] = Field(
        default=[],
        description="List of field names for multiple data series (for multi-bar charts)",
    )
    follow_up_suggestions: List[str] = Field(
        description="List of 1-2 follow-up suggestions based on available data & capability"
    )


class DatasetOption(BaseModel):
    dataset_id: int = Field(
        description="ID of the dataset that best matches the user query."
    )
    context_layer: Optional[str] = Field(
        None,
        description="Pick a single context layer from the dataset if useful",
    )
    reason: str = Field(
        description="Short reason why the dataset is the best match."
    )


class DatasetSelectionResult(DatasetOption):
    tile_url: str = Field(
        description="Tile URL of the dataset that best matches the user query.",
    )
    dataset_name: str = Field(
        description="Name of the dataset that best matches the user query."
    )
    analytics_api_endpoint: str = Field(
        description="Analytics API endpoint of the dataset that best matches the user query.",
    )
    description: str = Field(
        description="Description of the dataset that best matches the user query.",
    )
    prompt_instructions: str = Field(
        description="Prompt instructions of the dataset that best matches the user query.",
    )
    methodology: str = Field(
        description="Methodology of the dataset that best matches the user query.",
    )
    cautions: str = Field(
        description="Cautions of the dataset that best matches the user query.",
    )
    function_usage_notes: str = Field(
        description="Function usage notes of the dataset that best matches the user query.",
    )
    citation: str = Field(
        description="Citation of the dataset that best matches the user query.",
    )
