from src.agents.custom_prompt_registry import register_prompt_block
from src.agents.tools.custom.geo_query_geo_projects import (
    geo_query_geo_projects,  # noqa: F401 — triggers register_tool
)
from src.api.custom.geo_lake_county_projects_config import (
    get_geo_projects_prompt_block,
)

register_prompt_block(get_geo_projects_prompt_block)
