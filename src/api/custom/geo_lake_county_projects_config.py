from src.shared.lake_county_constants import (
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

GEO_PROJECTS_PROMPT_BLOCK = """
GEO LAKE COUNTY PROJECTS (when data_source is geo_lake_county and user asks about projects):

LAYER ARCHITECTURE:
- Representative points layer (FeatureServer/30): The primary layer containing ALL project attributes.
  Always call geo_discover_project_schema before filtering to know the exact field names and values.
- Geometry layers (fetched automatically by the tool after querying representative points):
    * FeatureServer/27 → Point geometries
    * FeatureServer/23 → Polyline/Line geometries
    * FeatureServer/29 → Polygon geometries
  Each shares `project_id` as the join key (NOT OBJECTID). The tool handles this internally.

PROJECT CATEGORIES — business-logic abstraction (NOT a schema field), pass via project_category=:
- "projects" (default): normal projects — excludes flood audits and studies
- "studies": study projects only
- "flood_audits": flood audit projects only
When user says "projects" without qualifiers, use "projects". When they say "studies" or "flood audits", use those.

TOOL: geo_query_geo_projects
Use for any query about projects in geo_lake_county mode.
ALWAYS call geo_discover_project_schema FIRST to know available fields before building any where_clause.

WORKFLOW for attribute-based project queries (type, status, cost, date, etc.):
1. Call geo_discover_project_schema() to inspect available fields, types, and domain values.
2. From the schema, deduce candidate_field_names: fields that could contain the user's values (e.g. for
   "approved" or "status" → status, ProjectStatus, last_status, etc.). Pass only field names that exist in the schema.
3. Call geo_resolve_attribute_filter(values=["Approved"], candidate_field_names=["status","ProjectStatus",...]).
   For multiple values (e.g. "approved and recommended"): values=["Approved","Recommended"].
4. The resolver returns the exact where_clause. Use it in geo_query_geo_projects(where_clause="<resolved_clause>", ...).
5. If the resolver says "values not found", ask the user to clarify — do NOT guess or try other fields.

WORKFLOW for "projects in [district/watershed/boundary]" (spatial filter):
1. Call geo_discover_layer_schema(layer_id="<boundary_layer_id>") to find the correct filter field.
2. Call geo_query_geo_projects(
     boundary_layer_id="<boundary_layer_id>",
     boundary_filter_field="<field_from_schema>",
     boundary_filter_value="<value>"
   )
Both workflows can be combined: pass both where_clause AND boundary_layer_id when needed.

EXAMPLES (illustrative — use geo_resolve_attribute_filter for attribute values):
- "show me all projects" → geo_discover_project_schema(), geo_query_geo_projects()
- "approved projects" → discover schema → geo_resolve_attribute_filter(values=["Approved"], candidate_field_names=["status","ProjectStatus",...]) → geo_query_geo_projects(where_clause=<resolved>)
- "approved and recommended projects" → geo_resolve_attribute_filter(values=["Approved","Recommended"], candidate_field_names=["status",...])
- "Capital projects" → geo_resolve_attribute_filter(values=["Capital"], candidate_field_names=["projecttype",...])
- "projects in Village of Antioch" → jurisdiction="Village of Antioch" (no attribute filter)
- "projects with final cost > 50000" → discover schema → build where_clause="<cost_field> > 50000" (numeric, no resolver)
- "projects in County Board District 5" → discover boundary layer schema → geo_query_geo_projects(boundary_layer_id="...", boundary_filter_field="<field>", boundary_filter_value="5")
- "show me studies" → project_category="studies"
- "flood audit projects" → project_category="flood_audits"

PROJECTS BY PERSON (submitted_by filter):
When the user asks for projects by a person's name (e.g. "Show me Adam's projects", "projects from Adam",
"Adam's projects"), pass submitted_by_user_name="Adam". The tool looks up the user in the inflow database
and filters by submitted_by. Only use when a person name is clearly mentioned — the first matching user is used.

MAP RENDERING:
- The tool emits geometry layers (colored by the project type field) and representative point markers.
- When boundary_layer_id is provided, the boundary polygon is shown automatically.
- When jurisdiction is provided (municipality queries), the municipality boundary is fetched and shown.

RICH CONTEXT (automatic):
- For modest result counts, the tool may attach narrative_enrichment: prose synthesized from long-text attribute
  fields chosen using the layer schema (types, aliases, domains) plus value length — not hardcoded field names.
- When present, it appears in the tool message and in the structured "Results detail" panel; ground your answer in it.

PROJECT INFO BY NAME (e.g. "give me info about Wadsworth Oaks"):
Call geo_get_project_geometry(project_name="<name>"). The tool returns attributes and displays
the project geometry on the map. Summarize the attributes in your response. Do NOT call
geo_spatial_intersection unless the user wants features within the project.

FINDING FEATURES WITHIN A NAMED PROJECT (e.g. "soils in Wadsworth Oaks project"):
When the user wants geo features (soils, streams, flood zones, etc.) within a named project:
1. Call geo_get_project_geometry(project_name="<name>") first.
2. Call geo_discover_layer_schema(layer_id="<what_layer>") to find the color/label field.
3. Call geo_spatial_intersection(
     where_layer_id="geo_project_geometry",
     where_filter_field="",
     where_filter_value="<project_name>",
     what_layer_id="<what_layer>",
     what_color_field="<field_from_schema>"
   )
Do NOT use geo_query_geo_projects for these flows.

IMPORTANT:
- For attribute value filters (status, type, etc.): ALWAYS use geo_resolve_attribute_filter — never guess the field.
- geo_resolve_attribute_filter fetches unique values from candidate fields in one query and returns the exact where_clause.
- If resolver says "values not found", ask the user to clarify — do NOT try other fields.
- Do NOT use geo_spatial_intersection or geo_query_layer for project queries — use geo_query_geo_projects.
- Do NOT call geo_build_result_summary after geo_query_geo_projects — it builds its own complete summary.
- project_id is the join key between the representative points and geometry layers (NOT OBJECTID).
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
