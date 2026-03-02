import custom  # noqa: F401 — registers all custom renderers
import folium
from custom_renderer_registry import get_renderer
from shapely.geometry import shape


def _compute_center_and_zoom(map_actions: list) -> tuple[list[float], int]:
    center = [42.34, -88.0]
    zoom_start = 10

    zoom_action = next((a for a in map_actions if a.get("type") == "zoomTo"), None)
    if zoom_action and zoom_action.get("geometry"):
        try:
            geom = shape(zoom_action["geometry"])
            minx, miny, maxx, maxy = geom.bounds
            center = [(miny + maxy) / 2, (minx + maxx) / 2]
            max_diff = max(maxy - miny, maxx - minx)
            if max_diff > 1.0:
                zoom_start = 8
            elif max_diff > 0.5:
                zoom_start = 9
            elif max_diff > 0.2:
                zoom_start = 10
            elif max_diff > 0.1:
                zoom_start = 11
            elif max_diff > 0.05:
                zoom_start = 12
            else:
                zoom_start = 13
        except Exception:
            pass

    return center, zoom_start


def render_geo_map(map_actions, width=700, height=400):
    if not map_actions:
        return None

    center, zoom_start = _compute_center_and_zoom(map_actions)
    m = folium.Map(location=center, zoom_start=zoom_start, tiles="OpenStreetMap")

    for action in map_actions:
        action_type = action.get("type")

        if action_type == "addBoundaryLayer":
            geojson_data = action.get("geojson")
            label = action.get("label", "Boundary")
            style = action.get("style", {})
            if geojson_data:
                folium.GeoJson(
                    geojson_data,
                    style_function=lambda feature, s=style: {
                        "fillColor": s.get("fillColor", "#004da8"),
                        "color": s.get("color", "#004da8"),
                        "weight": s.get("weight", 3),
                        "fillOpacity": s.get("fillOpacity", 0.0),
                    },
                    tooltip=label,
                    name=label,
                ).add_to(m)

        elif action_type == "addFeatureLayer":
            geojson_data = action.get("geojson")
            label = action.get("label", "Features")
            color_by_field = action.get("colorByField")
            color_palette = action.get("colorPalette") or []
            style = action.get("style", {})

            if geojson_data:
                if color_by_field and color_palette:
                    unique_values = sorted({
                        str(f.get("properties", {}).get(color_by_field))
                        for f in geojson_data.get("features", [])
                        if f.get("properties", {}).get(color_by_field) is not None
                    })
                    value_to_color = {
                        val: color_palette[i % len(color_palette)]
                        for i, val in enumerate(unique_values)
                    }

                    def style_function(feature, vtc=value_to_color, cbf=color_by_field, s=style):
                        val = str(feature.get("properties", {}).get(cbf, ""))
                        color = vtc.get(val, s.get("color", "#FF6B6B"))
                        return {
                            "fillColor": color,
                            "color": color,
                            "weight": s.get("weight", 1),
                            "fillOpacity": s.get("fillOpacity", 0.7),
                        }

                    folium.GeoJson(
                        geojson_data,
                        style_function=style_function,
                        tooltip=folium.GeoJsonTooltip(
                            fields=[color_by_field], aliases=[color_by_field]
                        ),
                        name=label,
                    ).add_to(m)
                else:
                    folium.GeoJson(
                        geojson_data,
                        style_function=lambda feature, s=style: {
                            "fillColor": s.get("fillColor", "#FF6B6B"),
                            "color": s.get("color", "#FF6B6B"),
                            "weight": s.get("weight", 2),
                            "fillOpacity": s.get("fillOpacity", 0.6),
                        },
                        tooltip=label,
                        name=label,
                    ).add_to(m)

        else:
            renderer = get_renderer(action_type)
            if renderer:
                renderer(m, action)

    folium.LayerControl().add_to(m)
    return m
