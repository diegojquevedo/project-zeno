from src.api.custom.geo_lake_county_projects_config import (
    GEO_PROJECT_AREAS_URL,
    GEO_PROJECT_LINES_URL,
    GEO_PROJECT_POINTS_URL,
    GEO_PROJECT_REPRESENTATIVE_POINTS_URL,
)
from src.shared.lake_county_constants import (
    GEO_LAKE_COUNTY_PROJECT_ID,
    LAKE_COUNTY_AOI,
    LAKE_COUNTY_BOUNDS,
    LAKE_COUNTY_CENTER,
    LAKE_COUNTY_ZOOM,
    LC_COUNTY_BOARD_DISTRICTS_URL,
    LC_DRAINAGE_DISTRICTS_URL,
    LC_HYDRO_LINES_URL,
    LC_MUNICIPALITIES_URL,
    LC_NFHL_FLOOD_ZONES_URL,
    LC_SAMPLING_SITES_URL,
    LC_SOILS_URL,
    LC_STATE_REP_DISTRICTS_URL,
    LC_STATE_SENATE_DISTRICTS_URL,
    LC_SUBWATERSHEDS_URL,
    LC_US_CONGRESSIONAL_DISTRICTS_URL,
    LC_WATERSHEDS_URL,
)

_GEO_LAYER_ID_ALIASES: dict[str, str] = {
    "smcallprojectpoints": "representative_points",
    "smc_all_project_points": "representative_points",
    "allprojectpoints": "representative_points",
    "lakecountysmcprojects": "representative_points",
    "smcprojects": "representative_points",
    "smcallprojectlines": "lines",
    "smcallprojectareas": "areas",
    "smcallprojectgeometrypoints": "points",
    "geo_project_representation_points": "representative_points",
    "project_rep_points": "representative_points",
}

GEO_LAKE_COUNTY_LAYERS = [
    {
        "layer_id": "municipalities",
        "arcgis_url": LC_MUNICIPALITIES_URL,
        "layer_type": "FeatureServer",
        "data_layer": "Municipalities",
        "dataset_name": "Municipalities",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Municipalities and jurisdictions in Lake County",
    },
    {
        "layer_id": "soils",
        "arcgis_url": LC_SOILS_URL,
        "layer_type": "MapServer",
        "data_layer": "Soils",
        "dataset_name": "Soils",
        "role": "what",
        "geometry_type": "polygon",
        "description": "NRCS soil types",
    },
    {
        "layer_id": "hydro_lines",
        "arcgis_url": LC_HYDRO_LINES_URL,
        "layer_type": "MapServer",
        "data_layer": "2002 Hydro Lines",
        "dataset_name": "2002 Hydro Lines",
        "role": "what",
        "geometry_type": "polyline",
        "description": "Hydrographic linear features (streams, rivers, lakes, ponds, drainage) in Lake County",
    },
    {
        "layer_id": "flood_zones",
        "arcgis_url": LC_NFHL_FLOOD_ZONES_URL,
        "layer_type": "MapServer",
        "data_layer": "NFHL Flood Zones",
        "dataset_name": "NFHL Flood Zones",
        "role": "what",
        "geometry_type": "polygon",
        "description": "FEMA National Flood Hazard Layer (NFHL) flood zones in Lake County (FLD_ZONE, ZONE_SUBTY, SFHA_TF)",
    },
    {
        "layer_id": "pollutant_sampling_sites",
        "arcgis_url": LC_SAMPLING_SITES_URL,
        "layer_type": "FeatureServer",
        "data_layer": "Pollutant Sampling Sites",
        "dataset_name": "Pollutant Sampling Sites",
        "role": "what",
        "geometry_type": "point",
        "value_field": "STATUS",
        "description": "Pollutant sampling sites with PCB, mercury, and water quality test results in Lake County",
    },
    {
        "layer_id": "county_board_districts",
        "arcgis_url": LC_COUNTY_BOARD_DISTRICTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "County Board Districts",
        "dataset_name": "County Board Districts",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Lake County Board of Commissioners districts",
    },
    {
        "layer_id": "drainage_districts",
        "arcgis_url": LC_DRAINAGE_DISTRICTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "Drainage Districts",
        "dataset_name": "Drainage Districts",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Drainage districts in Lake County",
    },
    {
        "layer_id": "watersheds",
        "arcgis_url": LC_WATERSHEDS_URL,
        "layer_type": "MapServer",
        "data_layer": "Watersheds",
        "dataset_name": "Watersheds",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Major watershed boundaries (e.g. Fox River, Des Plaines River)",
    },
    {
        "layer_id": "subwatersheds",
        "arcgis_url": LC_SUBWATERSHEDS_URL,
        "layer_type": "MapServer",
        "data_layer": "Subwatersheds",
        "dataset_name": "Subwatersheds",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Subwatershed boundaries (e.g. Upper Fox River, North Branch Chicago River)",
    },
    {
        "layer_id": "state_senate_districts",
        "arcgis_url": LC_STATE_SENATE_DISTRICTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "State Senate Districts",
        "dataset_name": "State Senate Districts",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Illinois State Senate districts in Lake County",
    },
    {
        "layer_id": "state_rep_districts",
        "arcgis_url": LC_STATE_REP_DISTRICTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "State Representative Districts",
        "dataset_name": "State Representative Districts",
        "role": "where",
        "geometry_type": "polygon",
        "description": "Illinois State Representative districts in Lake County",
    },
    {
        "layer_id": "us_congressional_districts",
        "arcgis_url": LC_US_CONGRESSIONAL_DISTRICTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "US Congressional Districts",
        "dataset_name": "US Congressional Districts",
        "role": "where",
        "geometry_type": "polygon",
        "description": "US Congressional districts in Lake County",
    },
    {
        "layer_id": "representative_points",
        "arcgis_url": GEO_PROJECT_REPRESENTATIVE_POINTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "SMC All Project representative points",
        "dataset_name": "Lake County SMC Projects (representative points)",
        "role": "projects",
        "geometry_type": "point",
        "description": "Lake County stormwater SMC projects: full attributes at representative points (FeatureServer/30). Use layer_id representative_points when geo_spatial_intersection WHAT layer is projects.",
    },
    {
        "layer_id": "points",
        "arcgis_url": GEO_PROJECT_POINTS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "SMC All Project points",
        "dataset_name": "Lake County SMC Projects (points)",
        "role": "projects",
        "geometry_type": "point",
        "description": "Project point geometries (FeatureServer/27), join key project_id",
    },
    {
        "layer_id": "lines",
        "arcgis_url": GEO_PROJECT_LINES_URL,
        "layer_type": "FeatureServer",
        "data_layer": "SMC All Project lines",
        "dataset_name": "Lake County SMC Projects (lines)",
        "role": "projects",
        "geometry_type": "polyline",
        "description": "Project line geometries (FeatureServer/23), join key project_id",
    },
    {
        "layer_id": "areas",
        "arcgis_url": GEO_PROJECT_AREAS_URL,
        "layer_type": "FeatureServer",
        "data_layer": "SMC All Project areas",
        "dataset_name": "Lake County SMC Projects (areas)",
        "role": "projects",
        "geometry_type": "polygon",
        "description": "Project area polygons (FeatureServer/29), join key project_id",
    },
]

GEO_LAKE_COUNTY_DEFAULT_LAYER = GEO_LAKE_COUNTY_LAYERS[0]
GEO_LAKE_COUNTY_LAYERS_BY_ID = {layer["layer_id"]: layer for layer in GEO_LAKE_COUNTY_LAYERS}

GEO_LAKE_COUNTY_LAYERS_BY_ROLE: dict[str, list[dict]] = {}
for layer in GEO_LAKE_COUNTY_LAYERS:
    role = layer.get("role", "what")
    GEO_LAKE_COUNTY_LAYERS_BY_ROLE.setdefault(role, []).append(layer)


def get_geo_lake_county_layers() -> list[dict]:
    return list(GEO_LAKE_COUNTY_LAYERS)


def normalize_geo_lake_county_layer_id(layer_id: str) -> str:
    if not layer_id or not str(layer_id).strip():
        return ""
    raw = str(layer_id).strip()
    return _GEO_LAYER_ID_ALIASES.get(raw.lower()) or raw


def get_geo_lake_county_layer_by_id(layer_id: str) -> dict | None:
    key = normalize_geo_lake_county_layer_id(layer_id)
    if not key:
        return None
    return GEO_LAKE_COUNTY_LAYERS_BY_ID.get(key)


def get_geo_lake_county_layers_by_role(role: str) -> list[dict]:
    return list(GEO_LAKE_COUNTY_LAYERS_BY_ROLE.get(role, []))


def get_geo_lake_county_where_layers() -> list[dict]:
    return get_geo_lake_county_layers_by_role("where")


def get_geo_lake_county_what_layers() -> list[dict]:
    return get_geo_lake_county_layers_by_role("what")


def get_geo_lake_county_project_layers() -> list[dict]:
    return get_geo_lake_county_layers_by_role("projects")


__all__ = [
    "GEO_LAKE_COUNTY_DEFAULT_LAYER",
    "GEO_LAKE_COUNTY_LAYERS",
    "GEO_LAKE_COUNTY_LAYERS_BY_ID",
    "GEO_LAKE_COUNTY_LAYERS_BY_ROLE",
    "GEO_LAKE_COUNTY_PROJECT_ID",
    "LAKE_COUNTY_AOI",
    "LAKE_COUNTY_BOUNDS",
    "LAKE_COUNTY_CENTER",
    "LAKE_COUNTY_ZOOM",
    "get_geo_lake_county_layer_by_id",
    "get_geo_lake_county_layers",
    "get_geo_lake_county_layers_by_role",
    "get_geo_lake_county_project_layers",
    "get_geo_lake_county_what_layers",
    "get_geo_lake_county_where_layers",
    "normalize_geo_lake_county_layer_id",
]
