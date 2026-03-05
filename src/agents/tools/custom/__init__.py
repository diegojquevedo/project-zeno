from src.agents.custom_prompt_registry import register_prompt_block
from src.agents.tools.custom.geo_discover_project_schema import (
    geo_discover_project_schema,  # noqa: F401 — triggers register_tool
)
from src.agents.tools.custom.geo_get_project_geometry import (
    geo_get_project_geometry,  # noqa: F401 — triggers register_tool
)
from src.agents.tools.custom.geo_query_geo_projects import (
    geo_query_geo_projects,  # noqa: F401 — triggers register_tool
)
from src.agents.tools.custom.geo_resolve_attribute_filter import (
    geo_resolve_attribute_filter,  # noqa: F401 — triggers register_tool
)
from src.api.custom.geo_lake_county_projects_config import (
    get_geo_projects_prompt_block,
)

register_prompt_block(get_geo_projects_prompt_block)
