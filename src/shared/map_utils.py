import colorsys

from shapely.geometry import shape

from src.shared.map_constants import (
    BOUNDARY_STYLE,
    DEFAULT_MAP_COLOR_PALETTE,
    FEATURE_STYLE,
    HSV_CONFIG,
    RGB_MAX_VALUE,
)


def generate_color_palette(unique_count: int) -> list[str]:
    """Generate a color palette for unique values."""
    if unique_count <= len(DEFAULT_MAP_COLOR_PALETTE):
        return DEFAULT_MAP_COLOR_PALETTE[:unique_count]

    colors = []
    for i in range(unique_count):
        hue = i / unique_count
        rgb = colorsys.hsv_to_rgb(hue, HSV_CONFIG["saturation"], HSV_CONFIG["value"])
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgb[0] * RGB_MAX_VALUE),
            int(rgb[1] * RGB_MAX_VALUE),
            int(rgb[2] * RGB_MAX_VALUE)
        )
        colors.append(hex_color)
    return colors


def create_zoom_to_action(geometry: dict) -> dict:
    """Create a zoomTo map action."""
    return {
        "type": "zoomTo",
        "geometry": geometry
    }


def create_set_basemap_action(basemap_id: str) -> dict:
    from src.shared.geo_basemap import GEO_BASEMAP_DEFAULT_ID, validate_basemap_id

    raw = (basemap_id or "").strip()
    bid = validate_basemap_id(raw) if raw else GEO_BASEMAP_DEFAULT_ID
    return {"type": "setBasemap", "basemap_id": bid}


def create_boundary_layer_action(
    geojson: dict,
    label: str,
    color: str = BOUNDARY_STYLE["color"],
    weight: int = BOUNDARY_STYLE["weight"],
    fill_opacity: float = BOUNDARY_STYLE["fill_opacity"]
) -> dict:
    """Create an addBoundaryLayer map action."""
    return {
        "type": "addBoundaryLayer",
        "geojson": geojson,
        "label": label,
        "style": {
            "color": color,
            "weight": weight,
            "fillOpacity": fill_opacity,
            "fillColor": color
        }
    }


def create_feature_layer_action(
    geojson: dict,
    label: str,
    color_by_field: str | None = None,
    color_palette: list[str] | None = None,
    default_color: str = FEATURE_STYLE["color"],
    weight: int = FEATURE_STYLE["weight"],
    fill_opacity: float = FEATURE_STYLE["fill_opacity"]
) -> dict:
    """Create an addFeatureLayer map action."""
    return {
        "type": "addFeatureLayer",
        "geojson": geojson,
        "label": label,
        "colorByField": color_by_field,
        "colorPalette": color_palette,
        "style": {
            "color": default_color,
            "weight": weight,
            "fillOpacity": fill_opacity,
            "fillColor": default_color
        }
    }


def calculate_bounds_from_geojson(geojson: dict) -> tuple[float, float, float, float] | None:
    """Calculate bounding box from GeoJSON."""
    try:
        features = geojson.get("features", [])
        if not features:
            return None

        all_bounds = []
        for feature in features:
            geom = feature.get("geometry")
            if geom:
                shp = shape(geom)
                all_bounds.append(shp.bounds)

        if not all_bounds:
            return None

        minx = min(b[0] for b in all_bounds)
        miny = min(b[1] for b in all_bounds)
        maxx = max(b[2] for b in all_bounds)
        maxy = max(b[3] for b in all_bounds)

        return (minx, miny, maxx, maxy)
    except Exception:
        return None


def extract_unique_values(geojson: dict, field_name: str) -> list[str]:
    """Extract unique values for a field from GeoJSON features."""
    values = set()
    for feature in geojson.get("features", []):
        value = feature.get("properties", {}).get(field_name)
        if value is not None:
            values.add(str(value))
    return sorted(list(values))
