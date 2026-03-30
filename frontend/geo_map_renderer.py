import custom  # noqa: F401 — registers all custom renderers
import folium
from custom_renderer_registry import get_renderer
from shapely.geometry import shape

from constants import (
    FOLIUM_ZOOMFIT_MAX_ZOOM,
    FOLIUM_ZOOMFIT_PADDING_PX,
    FOLIUM_ZOOMFIT_POINT_BUFFER_DEG,
)


def _expand_degenerate_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    buf: float,
) -> tuple[float, float, float, float]:
    dx = maxx - minx
    dy = maxy - miny
    if dx < 1e-9 and dy < 1e-9:
        return minx - buf, miny - buf, maxx + buf, maxy + buf
    if dx < 1e-8:
        minx -= buf
        maxx += buf
    if dy < 1e-8:
        miny -= buf
        maxy += buf
    return minx, miny, maxx, maxy


def _sw_ne_bounds_from_zoom_geometry(raw: dict) -> list[list[float]] | None:
    try:
        from shapely.ops import unary_union

        if raw.get("type") == "FeatureCollection":
            shapes = [
                shape(f["geometry"])
                for f in raw.get("features", [])
                if f.get("geometry")
            ]
            geom = unary_union(shapes) if shapes else None
        else:
            geom = shape(raw)
        if geom is None or geom.is_empty:
            return None
        minx, miny, maxx, maxy = geom.bounds
        minx, miny, maxx, maxy = _expand_degenerate_bounds(
            minx,
            miny,
            maxx,
            maxy,
            FOLIUM_ZOOMFIT_POINT_BUFFER_DEG,
        )
        return [[miny, minx], [maxy, maxx]]
    except Exception:
        return None


def _compute_center_and_zoom(map_actions: list) -> tuple[list[float], int]:
    center = [42.34, -88.0]
    zoom_start = 10

    zoom_action = next((a for a in map_actions if a.get("type") == "zoomTo"), None)
    if zoom_action and zoom_action.get("geometry"):
        try:
            raw = zoom_action["geometry"]
            if raw.get("type") == "FeatureCollection":
                from shapely.ops import unary_union

                shapes = [
                    shape(f["geometry"])
                    for f in raw.get("features", [])
                    if f.get("geometry")
                ]
                geom = unary_union(shapes) if shapes else None
            else:
                geom = shape(raw)
            if geom is None:
                raise ValueError("empty geometry")
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
            elif max_diff > 0.02:
                zoom_start = 14
            elif max_diff > 0.008:
                zoom_start = 16
            else:
                zoom_start = 17
        except Exception:
            pass

    return center, zoom_start


def render_geo_map(map_actions, width: int | str | None = 700, height=400):
    if not map_actions:
        return None

    map_width: int | str = "100%" if width is None else width

    center, zoom_start = _compute_center_and_zoom(map_actions)
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        width=map_width,
        height=height,
    )

    zoom_action = next((a for a in map_actions if a.get("type") == "zoomTo"), None)
    if zoom_action and zoom_action.get("geometry"):
        sw_ne = _sw_ne_bounds_from_zoom_geometry(zoom_action["geometry"])
        if sw_ne:
            pad = FOLIUM_ZOOMFIT_PADDING_PX
            m.fit_bounds(
                sw_ne,
                padding_top_left=(pad, pad),
                padding_bottom_right=(pad, pad),
                max_zoom=FOLIUM_ZOOMFIT_MAX_ZOOM,
            )

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

    folium.LayerControl(position="bottomleft").add_to(m)
    return m
