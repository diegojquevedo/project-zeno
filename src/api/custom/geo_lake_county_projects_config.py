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
  Always call geo_discover_project_schema before filtering so field names and domains come from the live layer.
- Geometry layers (fetched automatically by the tool after querying representative points):
    * FeatureServer/27 → Point geometries
    * FeatureServer/23 → Polyline/Line geometries
    * FeatureServer/29 → Polygon geometries
  Each shares `project_id` as the join key (NOT OBJECTID). The tool handles this internally.

PROJECT CATEGORIES — business-logic abstraction (NOT a schema field), pass via project_category=:
- "projects" (default): normal projects — excludes flood audits and studies
- "studies": study projects only
- "flood_audits": flood audit projects only
When the user says "studies", "study projects", "flood audit", or "flood audit projects", use project_category only — do not treat the leading words as free-text attribute values to resolve.
Otherwise default project_category to "projects" when they mean ordinary stormwater projects.

QUALIFIER BEFORE "PROJECTS" (lifecycle / state / category words):
When the user attaches a word or short phrase immediately before "projects" (or the same idea in Spanish or shorthand), and that phrase is not the studies/flood-audit case above, treat the phrase as one or more discrete values that might appear in a categorical column — but the correct column is unknown until you read the layer schema.
Mandatory sequence:
1. geo_discover_project_schema — use fields, types, aliases, and coded domains from the response only. Never invent field names; schemas change.
2. candidate_field_names: list only names that appear in that schema. Prefer string fields with coded domains, or names/aliases suggesting category, lifecycle, workflow, phase, approval, program, or funding/type. Omit geometry columns, opaque IDs, and huge narrative text fields unless the user clearly gave a long exact phrase. Order from most plausible (domain-backed category-like) to broader; geo_resolve_attribute_filter checks fields in list order.
3. geo_resolve_attribute_filter(values=[...], candidate_field_names=[...]) — values are the user's word(s), split sensibly for several tokens joined by "and"/"or". The tool loads distinct values for those columns and returns a single where_clause when all values match one field.
4. geo_query_geo_projects(..., where_clause=<from resolver>). If the resolver says values were not found, use its hints and ask the user — do not silently query without that filter or assign a column from memory.

Numeric or date predicates (greater than, less than, between): discover the field from the schema and build the where_clause from types yourself; the resolver is for discrete stored values.

TOOL: geo_query_geo_projects
Use for any project listing or count in geo_lake_county mode. For user-given categorical words, obtain where_clause from geo_resolve_attribute_filter after discovery — do not assume which attribute holds those words.

WORKFLOW for "projects in [district/watershed/boundary]" (spatial filter):
1. Call geo_discover_layer_schema(layer_id="<boundary_layer_id>") to find the correct filter field.
2. Call geo_query_geo_projects(
     boundary_layer_id="<boundary_layer_id>",
     boundary_filter_field="<field_from_schema>",
     boundary_filter_value="<value>"
   )
You may combine this with a resolver-produced where_clause and jurisdiction arguments in one geo_query_geo_projects call when the question asks for both.

ILLUSTRATIVE PATTERNS (all field names must be copied from the current schema):
- Broad project list → geo_discover_project_schema, geo_query_geo_projects(project_category="projects") or equivalent default.
- "<USER_WORD> projects" → discover schema → build candidate_field_names from that schema → geo_resolve_attribute_filter(values=["<USER_WORD>"], candidate_field_names=[...]) → geo_query_geo_projects(where_clause=resolved).
- Several values for one attribute → one resolver call with values=[...] if the tool must match all of them on the same field.
- "projects in <municipality>" without an extra qualifier → jurisdiction= or boundary flow using boundary-layer schema.
- "projects in County Board District 5" → boundary layer schema → geo_query_geo_projects(boundary_layer_id="...", boundary_filter_field="<field>", boundary_filter_value="5").

PROJECTS BY PERSON (submitted_by filter):
When the user asks for projects by a person's name (e.g. "Show me Adam's projects", "projects from Adam",
"Adam's projects"), pass submitted_by_user_name="Adam". The tool looks up the user in the inflow database
and filters by submitted_by. Only use when a person name is clearly mentioned — the first matching user is used.

MAP BASEMAP (geo_query_geo_projects, parameter basemap_id):
- User messages may include [Map state] with the current active_basemap_id. Use it for relative wording such as
  clearer, lighter, darker, night, satellite, terrain, or obvious typos (e.g. terra → terrain / open_topo).
- Pass basemap_id as exactly one of: openstreetmap, carto_positron, carto_dark, open_topo, esri_imagery.
  You choose the id from natural language; the server does not parse free-form basemap names.
- Omit basemap_id entirely when the user does not ask to change the map background (previous basemap is kept).

MAP RENDERING:
- The tool emits geometry layers (styled using layer configuration) and representative point markers.
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
- Any user-supplied label that should match stored categorical values on the project layer: resolver first; never pick the column name from memory or from older docs.
- geo_resolve_attribute_filter fetches distinct values only for the candidate columns you pass; it returns the where_clause or asks for clarification.
- Do NOT use geo_spatial_intersection or geo_query_layer for listing/filtering projects — use geo_query_geo_projects.
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
