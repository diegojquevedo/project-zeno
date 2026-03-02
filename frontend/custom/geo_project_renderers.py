import folium
from custom_renderer_registry import register_renderer

_TOOLTIP_FIELDS = ["Name", "projecttype", "status", "jurisdiction"]


def _build_tooltip_html(props: dict, fields: list[str]) -> str:
    rows = "".join(
        f"<tr><td style='padding:2px 6px;font-weight:bold'>{f}</td>"
        f"<td style='padding:2px 6px'>{props.get(f, '')}</td></tr>"
        for f in fields
        if props.get(f) is not None
    )
    return f"<table style='font-size:12px'>{rows}</table>"


def _active_tooltip_fields(geojson_data: dict) -> list[str]:
    available: set[str] = set()
    for feat in geojson_data.get("features", []):
        available.update(feat.get("properties", {}).keys())
    return [f for f in _TOOLTIP_FIELDS if f in available]


def _render_project_geometry_layer(m: folium.Map, action: dict) -> None:
    geojson_data = action.get("geojson")
    label = action.get("label", "Project Geometries")
    default_color = action.get("defaultColor", "#00ffff")

    if not geojson_data:
        return

    fields = _active_tooltip_fields(geojson_data)

    def style_fn(feature, dc=default_color):
        color = feature.get("properties", {}).get("_color", dc)
        return {
            "fillColor": color,
            "color": color,
            "weight": 2,
            "fillOpacity": 0.45,
            "opacity": 0.9,
        }

    folium.GeoJson(
        geojson_data,
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=fields) if fields else None,
        name=label,
    ).add_to(m)


def _render_project_rep_points_layer(m: folium.Map, action: dict) -> None:
    geojson_data = action.get("geojson")
    label = action.get("label", "Project Reference Points")
    default_color = action.get("defaultColor", "#00ffff")

    if not geojson_data:
        return

    fields = _active_tooltip_fields(geojson_data)
    feature_group = folium.FeatureGroup(name=label)

    for feat in geojson_data.get("features", []):
        geom = feat.get("geometry")
        props = feat.get("properties", {})
        if not geom or geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        color = props.get("_color", default_color)
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            opacity=1.0,
            tooltip=folium.Tooltip(_build_tooltip_html(props, fields)),
        ).add_to(feature_group)

    feature_group.add_to(m)


register_renderer("addProjectGeometryLayer", _render_project_geometry_layer)
register_renderer("addProjectRepPointsLayer", _render_project_rep_points_layer)
