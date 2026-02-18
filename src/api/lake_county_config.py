"""
Lake County ArcGIS layer configuration (Projects).
Approved and submitted projects use the same geometry layers; status is a filter.
"""

# Bounds from Project_to_analyze: [[-88.33, 41.99], [-87.67, 42.69]]
LAKE_COUNTY_BOUNDS = [[-88.33, 41.99], [-87.67, 42.69]]
LAKE_COUNTY_CENTER = [42.34, -88.0]
LAKE_COUNTY_ZOOM = 10

SMC_API_BASE = "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services"

# Project layers (FeatureServer) - includes approved and submitted projects
LAKE_COUNTY_LAYERS = [
    {
        "layer_id": "project_points",
        "dataset_name": "Project Points",
        "data_layer": "Project Points",
        "arcgis_url": f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/27",
        "layer_type": "FeatureServer",
        "geometry_type": "point",
        "source": "Lake County",
        "description": "Point locations of stormwater projects (approved and submitted) in Lake County.",
    },
    {
        "layer_id": "project_areas",
        "dataset_name": "Project Areas",
        "data_layer": "Project Areas",
        "arcgis_url": f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/29",
        "layer_type": "FeatureServer",
        "geometry_type": "polygon",
        "source": "Lake County",
        "description": "Area geometries of stormwater projects (approved and submitted) in Lake County.",
    },
    {
        "layer_id": "project_lines",
        "dataset_name": "Project Lines",
        "data_layer": "Project Lines",
        "arcgis_url": f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/23",
        "layer_type": "FeatureServer",
        "geometry_type": "polyline",
        "source": "Lake County",
        "description": "Linear geometries of stormwater projects (approved and submitted) in Lake County.",
    },
    {
        "layer_id": "project_representative_points",
        "dataset_name": "Project Representative Points",
        "data_layer": "Project Representative Points",
        "arcgis_url": f"{SMC_API_BASE}/SMCAllProjectLayers/FeatureServer/30",
        "layer_type": "FeatureServer",
        "geometry_type": "point",
        "source": "Lake County",
        "description": "Representative point locations of stormwater projects in Lake County.",
    },
]

LAKE_COUNTY_LAYERS_BY_ID = {l["layer_id"]: l for l in LAKE_COUNTY_LAYERS}

# Layer used for project search by name (has Name field)
LAKE_COUNTY_SEARCH_LAYER_ID = "project_representative_points"

# Lake County Boundary - use PoliticalBoundaries (services3 responds; maps.lakecountyil.gov times out)
LC_BOUNDARY_URL = f"{SMC_API_BASE}/LakeCounty_PoliticalBoundaries/FeatureServer/2"

# Municipal Boundaries - for highlighting jurisdiction outline when filtering by jurisdiction
LC_MUNICIPALITIES_URL = f"{SMC_API_BASE}/LakeCounty_TaxDistricts/FeatureServer/10"

# Pre-Applications (PreApps) - status <> 'Archived'
# Layer 98: metadata + points (one record per preapp)
# Layer 99: polygon/line geometries (by preapp_id)
PREAPP_POINT_URL = f"{SMC_API_BASE}/PreApplicationProjectLocation/FeatureServer/98"
PREAPP_GEOMETRY_URL = f"{SMC_API_BASE}/PreApplicationProjectLocation/FeatureServer/99"

# When user says "Chicago" in Lake County, they mean North Chicago (Chicago proper is in Cook County)
JURISDICTION_ALIASES = {"chicago": "North Chicago"}

# Concerns (CIRS) - status_CIRS <> 'Archived', point geometry only
CIRS_POINT_URL = f"{SMC_API_BASE}/CIRS_Point/FeatureServer/6"

# Map Geometry attribute (from layer 30) to geometry layer_id
GEOMETRY_TYPE_TO_LAYER = {
    "Polygon": "project_areas",
    "Point": "project_points",
    "Polyline": "project_lines",
    "Line": "project_lines",
}

# System purpose (for agent reasoning context)
LAKE_COUNTY_SYSTEM_PURPOSE = (
    "INFLOW! is the Lake County Stormwater Management Commission's intake platform for "
    "stormwater projects. Projects address drainage, flood damages, water quality, and stormwater infrastructure."
)

# INFLOW project categories (matches tabs: Projects, Studies, Flood Audits)
# - projects: projectsubtype <> 'Flood Audit' AND projectsubtype <> 'Study' (and null)
# - studies: is_study = 1 (projectsubtype not updated for studies)
# - flood_audits: projectsubtype = 'Flood Audit'
PROJECT_CATEGORY_PROJECTS = "projects"  # Normal projects (536 in INFLOW)
PROJECT_CATEGORY_STUDIES = "studies"  # Studies (69 in INFLOW)
PROJECT_CATEGORY_FLOOD_AUDITS = "flood_audits"  # Flood Audits (274 in INFLOW)

# Project type definitions (for agent reasoning - maps user semantic queries to project_types)
LAKE_COUNTY_PROJECT_TYPE_DEFINITIONS = [
    ("Capital", "Master planned improvements that resolve multi-jurisdictional drainage and flood damages and preserve water quality."),
    ("WMB", "Plans to identify and help reduce flood damages and improve water quality."),
    ("SIRF", "Plans to help improve and/or restore stormwater infrastructure."),
    ("319", "Nonpoint Source Pollution Control program to protect water quality in Illinois."),
    ("WMAG", "Plans to support local watershed partnerships in Lake County."),
    ("Maintenance", "Restore existing infrastructure eligible for SMC participation."),
    ("Other", "Any other effort for which SMC funds or staff time is requested."),
]
