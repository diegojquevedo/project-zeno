from src.shared.lake_county_constants import (
    GEO_LAKE_COUNTY_PROJECT_ID,
    LAKE_COUNTY_AOI,
    LAKE_COUNTY_BOUNDS,
    LAKE_COUNTY_CENTER,
    LAKE_COUNTY_ZOOM,
    LC_MUNICIPALITIES_URL,
    LC_SOILS_URL,
)

GEO_LAKE_COUNTY_LAYERS = [
    {
        "layer_id": "municipalities",
        "arcgis_url": LC_MUNICIPALITIES_URL,
        "layer_type": "FeatureServer",
        "data_layer": "Municipalities",
        "dataset_name": "Municipalities",
        "role": "where",
        "label_field": "NAME",
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
        "value_field": "SOILCODE",
        "geometry_type": "polygon",
        "description": "NRCS soil types",
    },
]

GEO_LAKE_COUNTY_DEFAULT_LAYER = GEO_LAKE_COUNTY_LAYERS[0]
GEO_LAKE_COUNTY_LAYERS_BY_ID = {l["layer_id"]: l for l in GEO_LAKE_COUNTY_LAYERS}

GEO_LAKE_COUNTY_LAYERS_BY_ROLE: dict[str, list[dict]] = {}
for layer in GEO_LAKE_COUNTY_LAYERS:
    role = layer.get("role", "what")
    GEO_LAKE_COUNTY_LAYERS_BY_ROLE.setdefault(role, []).append(layer)


def get_geo_lake_county_layers() -> list[dict]:
    return list(GEO_LAKE_COUNTY_LAYERS)


def get_geo_lake_county_layer_by_id(layer_id: str) -> dict | None:
    return GEO_LAKE_COUNTY_LAYERS_BY_ID.get(layer_id)


def get_geo_lake_county_layers_by_role(role: str) -> list[dict]:
    return list(GEO_LAKE_COUNTY_LAYERS_BY_ROLE.get(role, []))


def get_geo_lake_county_where_layers() -> list[dict]:
    return get_geo_lake_county_layers_by_role("where")


def get_geo_lake_county_what_layers() -> list[dict]:
    return get_geo_lake_county_layers_by_role("what")


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
    "get_geo_lake_county_what_layers",
    "get_geo_lake_county_where_layers",
]
