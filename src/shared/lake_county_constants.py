LAKE_COUNTY_BOUNDS = [[-88.33, 41.99], [-87.67, 42.69]]
LAKE_COUNTY_CENTER = [42.34, -88.0]
LAKE_COUNTY_ZOOM = 10


def _get_smc_api_base() -> str:
    from src.core.config import settings
    return settings.smc_api_base


SMC_API_BASE = _get_smc_api_base()

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

LAKE_COUNTY_LAYERS_BY_ID = {layer["layer_id"]: layer for layer in LAKE_COUNTY_LAYERS}

LAKE_COUNTY_SEARCH_LAYER_ID = "project_representative_points"

LC_BOUNDARY_URL = f"{SMC_API_BASE}/LakeCounty_PoliticalBoundaries/FeatureServer/2"

LC_MUNICIPALITIES_URL = f"{SMC_API_BASE}/LakeCounty_TaxDistricts/FeatureServer/10"

LC_COUNTY_BOARD_DISTRICTS_URL = f"{SMC_API_BASE}/LakeCounty_PoliticalBoundaries/FeatureServer/0"
LC_DRAINAGE_DISTRICTS_URL = f"{SMC_API_BASE}/LakeCounty_TaxDistricts/FeatureServer/1"
LC_STATE_SENATE_DISTRICTS_URL = f"{SMC_API_BASE}/LakeCounty_PoliticalBoundaries/FeatureServer/5"
LC_STATE_REP_DISTRICTS_URL = f"{SMC_API_BASE}/LakeCounty_PoliticalBoundaries/FeatureServer/4"
LC_US_CONGRESSIONAL_DISTRICTS_URL = f"{SMC_API_BASE}/LakeCounty_PoliticalBoundaries/FeatureServer/6"

WAB_DRAINAGE_MAP_SERVER = "https://maps.lakecountyil.gov/arcgis/rest/services/GISMapping/WABDrainage/MapServer"
LC_WATERSHEDS_URL = f"{WAB_DRAINAGE_MAP_SERVER}/7"
LC_SUBWATERSHEDS_URL = f"{WAB_DRAINAGE_MAP_SERVER}/8"

LC_SOILS_URL = "https://maps.lakecountyil.gov/arcgis/rest/services/GISMapping/WABSoil/MapServer/4"
LC_HYDRO_LINES_URL = "https://maps.lakecountyil.gov/arcgis/rest/services/GISMapping/WABWater/MapServer/4"
LC_NFHL_FLOOD_ZONES_URL = "https://maps.lakecountyil.gov/arcgis/rest/services/GISMapping/NFHL/MapServer/28"
LC_SAMPLING_SITES_URL = "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/SamplingSites/FeatureServer/0"

PREAPP_POINT_URL = f"{SMC_API_BASE}/PreApplicationProjectLocation/FeatureServer/98"
PREAPP_GEOMETRY_URL = f"{SMC_API_BASE}/PreApplicationProjectLocation/FeatureServer/99"

JURISDICTION_ALIASES = {"chicago": "North Chicago"}

CIRS_POINT_URL = f"{SMC_API_BASE}/CIRS_Point/FeatureServer/6"

GEOMETRY_TYPE_TO_LAYER = {
    "Polygon": "project_areas",
    "Point": "project_points",
    "Polyline": "project_lines",
    "Line": "project_lines",
}

LAKE_COUNTY_SYSTEM_PURPOSE = (
    "INFLOW! is the Lake County Stormwater Management Commission's intake platform for "
    "stormwater projects. Projects address drainage, flood damages, water quality, and stormwater infrastructure."
)

PROJECT_CATEGORY_PROJECTS = "projects"
PROJECT_CATEGORY_STUDIES = "studies"
PROJECT_CATEGORY_FLOOD_AUDITS = "flood_audits"

LAKE_COUNTY_PROJECT_TYPE_DEFINITIONS = [
    ("Capital", "Master planned improvements that resolve multi-jurisdictional drainage and flood damages and preserve water quality."),
    ("WMB", "Plans to identify and help reduce flood damages and improve water quality."),
    ("SIRF", "Plans to help improve and/or restore stormwater infrastructure."),
    ("319", "Nonpoint Source Pollution Control program to protect water quality in Illinois."),
    ("WMAG", "Plans to support local watershed partnerships in Lake County."),
    ("Maintenance", "Restore existing infrastructure eligible for SMC participation."),
    ("Other", "Any other effort for which SMC funds or staff time is requested."),
]

LAKE_COUNTY_AOI = {
    "source": "lake_county",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [-88.33, 41.99],
            [-87.67, 41.99],
            [-87.67, 42.69],
            [-88.33, 42.69],
            [-88.33, 41.99],
        ]],
    },
}

GEO_LAKE_COUNTY_PROJECT_ID = "geo_lake_county"
