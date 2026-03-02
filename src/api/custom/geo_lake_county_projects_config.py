from src.shared.lake_county_constants import (
    LAKE_COUNTY_PROJECT_TYPE_DEFINITIONS,
    PROJECT_CATEGORY_FLOOD_AUDITS,
    PROJECT_CATEGORY_PROJECTS,
    PROJECT_CATEGORY_STUDIES,
    SMC_API_BASE,
)

GEO_PROJECT_REPRESENTATIVE_POINTS_URL = f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/30"
GEO_PROJECT_POINTS_URL = f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/27"
GEO_PROJECT_LINES_URL = f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/23"
GEO_PROJECT_AREAS_URL = f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/29"

GEO_PROJECT_LAYERS: dict[str, str] = {
    "representative_points": GEO_PROJECT_REPRESENTATIVE_POINTS_URL,
    "points": GEO_PROJECT_POINTS_URL,
    "lines": GEO_PROJECT_LINES_URL,
    "areas": GEO_PROJECT_AREAS_URL,
}

GEO_PROJECT_GEOMETRY_FIELD = "Geometry"

GEO_PROJECT_GEOM_TYPE_TO_LAYER: dict[str, str] = {
    "Point": "points",
    "Polyline": "lines",
    "Line": "lines",
    "Polygon": "areas",
}

GEO_PROJECT_ID_FIELD = "project_id"

GEO_PROJECT_TYPE_FIELD = "projecttype"

GEO_PROJECT_TYPE_COLORS: dict[str, str] = {
    "319": "#4caf50",
    "Capital": "#ffeb3b",
    "Maintenance": "#87ceeb",
    "Multiple Funding Sources": "#da70d6",
    "Other": "#ff9800",
    "SIRF": "#8a2be2",
    "WMAG": "#9470da",
    "WMB": "#2196f3",
}

GEO_PROJECT_DEFAULT_COLOR = "#00ffff"

GEO_PROJECT_CATEGORY_PROJECTS = PROJECT_CATEGORY_PROJECTS
GEO_PROJECT_CATEGORY_STUDIES = PROJECT_CATEGORY_STUDIES
GEO_PROJECT_CATEGORY_FLOOD_AUDITS = PROJECT_CATEGORY_FLOOD_AUDITS

_project_type_lines = [
    f"  - {name}: {desc}"
    for name, desc in LAKE_COUNTY_PROJECT_TYPE_DEFINITIONS
]

GEO_PROJECTS_PROMPT_BLOCK = f"""
GEO LAKE COUNTY PROJECTS (when data_source is geo_lake_county and user asks about projects):

LAYER ARCHITECTURE:
- Representative points layer (FeatureServer/30): Contains ALL project attributes — Name, projecttype,
  projectsubtype, status, ProjectStatus, jurisdiction, Subshed, ProjectPartners, is_study, Geometry, project_id, etc.
  This is the primary search/filter layer. Always query this layer first.
- Geometry layers (fetched in parallel after attribute query):
    * FeatureServer/27 → Point geometries  (Geometry field = "Point")
    * FeatureServer/23 → Polyline geometries (Geometry field = "Polyline" or "Line")
    * FeatureServer/29 → Polygon geometries (Geometry field = "Polygon")
  Each geometry layer shares `project_id` as the join key (NOT OBJECTID).

PROJECT CATEGORIES (filter on representative points layer):
- "projects" → normal projects: excludes Flood Audit and Study
    SQL: (projectsubtype IS NULL OR projectsubtype <> 'Flood Audit') AND (is_study IS NULL OR is_study = 0)
- "studies" → study projects: is_study = 1
- "flood_audits" → flood audit projects: projectsubtype = 'Flood Audit'
- If no category specified and user says "projects", default to "projects" category.

PROJECT TYPES (projecttype field — used for coloring on map):
{chr(10).join(_project_type_lines)}

TOOL: geo_query_geo_projects
Use this tool when the user asks about projects in geo_lake_county mode:
- "show me all projects in Lake County" → project_category="projects"
- "show me Capital projects" → project_types=["Capital"]
- "projects in Antioch" → jurisdiction="Antioch"
- "show me studies" → project_category="studies"
- "flood audit projects" → project_category="flood_audits"
- "show me WMB and SIRF projects" → project_types=["WMB", "SIRF"]
- "projects with status Recommended" → status="Recommended"

MAP RENDERING:
- For each project returned, the tool emits TWO map layers:
  1. The actual geometry (polygon, polyline, or point) colored by projecttype
  2. The representative point (always shown as a distinct marker)
- Both layers use the projecttype field for coloring.
- Color mapping by projecttype: {", ".join(f"{k}={v}" for k, v in GEO_PROJECT_TYPE_COLORS.items())}
- Default color for unknown types: {GEO_PROJECT_DEFAULT_COLOR}

IMPORTANT:
- Do NOT use geo_spatial_intersection or geo_query_layer for project queries — use geo_query_geo_projects
- Do NOT hardcode project_id values — always query dynamically
- Geometry fetch is done in parallel batches by the tool automatically
- project_id is the join key between representative points and geometry layers (NOT OBJECTID)
"""


def get_geo_projects_prompt_block() -> str:
    return GEO_PROJECTS_PROMPT_BLOCK


__all__ = [
    "GEO_PROJECT_CATEGORY_FLOOD_AUDITS",
    "GEO_PROJECT_CATEGORY_PROJECTS",
    "GEO_PROJECT_CATEGORY_STUDIES",
    "GEO_PROJECT_DEFAULT_COLOR",
    "GEO_PROJECT_GEOM_TYPE_TO_LAYER",
    "GEO_PROJECT_GEOMETRY_FIELD",
    "GEO_PROJECT_ID_FIELD",
    "GEO_PROJECT_LAYERS",
    "GEO_PROJECT_REPRESENTATIVE_POINTS_URL",
    "GEO_PROJECT_TYPE_COLORS",
    "GEO_PROJECT_TYPE_FIELD",
    "get_geo_projects_prompt_block",
]
