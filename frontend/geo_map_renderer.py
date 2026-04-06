import custom  # noqa: F401 — registers all custom renderers
import folium
import streamlit as st
from branca.element import MacroElement
from custom_renderer_registry import get_renderer
from jinja2 import Template
from shapely.geometry import shape

from constants import (
    FOLIUM_ZOOMFIT_MAX_ZOOM,
    FOLIUM_ZOOMFIT_PADDING_PX,
    FOLIUM_ZOOMFIT_POINT_BUFFER_DEG,
    SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW,
    SESSION_KEY_GEO_RESULT_SUMMARY,
)
from src.shared.geo_basemap import (
    GEO_BASEMAP_DEFAULT_ID,
    GEO_BASEMAP_SPECS,
    validate_basemap_id,
)

_STREAMLIT_FOLIUM_RESIZE_MACRO = Template(
    """
{% macro script(this, kwargs) %}
{% raw %}
(function () {
    var win = window;
    function invalidateLeafletMaps() {
        try {
            for (var k in win) {
                if (!Object.prototype.hasOwnProperty.call(win, k) || k.indexOf("map_") !== 0) {
                    continue;
                }
                var mm = win[k];
                if (mm && typeof mm.invalidateSize === "function") {
                    mm.invalidateSize({ animate: false });
                }
            }
        } catch (e0) {}
    }
    function stretchLayout() {
        try {
            var fe = null;
            try {
                fe = win.frameElement;
            } catch (eFe) {}
            var fromFrame = 0;
            if (fe) {
                fromFrame = Math.floor(fe.getBoundingClientRect().height);
                if (fromFrame < 1) {
                    fromFrame = Math.floor(fe.clientHeight);
                }
            }
            var inner = Math.floor(win.innerHeight ?? 0);
            var docEl = document.documentElement;
            var clientDoc = docEl ? Math.floor(docEl.clientHeight) : 0;
            var h = Math.max(80, fromFrame, inner, clientDoc);
            if (h < 120) {
                var bc = document.body ? document.body.clientHeight : 0;
                h = Math.max(120, Math.floor(bc));
            }
            var html = document.documentElement;
            if (html) {
                html.style.setProperty("height", h + "px", "important");
                html.style.setProperty("max-height", h + "px", "important");
                html.style.setProperty("overflow", "hidden", "important");
            }
            var body = document.body;
            if (body) {
                body.style.setProperty("height", h + "px", "important");
                body.style.setProperty("max-height", h + "px", "important");
                body.style.setProperty("overflow", "hidden", "important");
                body.style.setProperty("margin", "0", "important");
            }
            var root = document.getElementById("root");
            if (root) {
                root.style.setProperty("height", h + "px", "important");
                root.style.setProperty("max-height", h + "px", "important");
                root.style.setProperty("overflow", "hidden", "important");
                root.style.setProperty("display", "flex", "important");
                root.style.setProperty("flex-direction", "column", "important");
                root.style.setProperty("min-height", "0", "important");
            }
            var parentEl = document.getElementById("parent") || document.querySelector(".float-container");
            if (parentEl) {
                parentEl.style.setProperty("float", "none", "important");
                parentEl.style.setProperty("display", "flex", "important");
                parentEl.style.setProperty("flex-direction", "column", "important");
                parentEl.style.setProperty("height", "100%", "important");
                parentEl.style.setProperty("min-height", "0", "important");
                parentEl.style.setProperty("flex", "1 1 0", "important");
                parentEl.style.setProperty("overflow", "hidden", "important");
                parentEl.style.setProperty("width", "100%", "important");
                var fc = parentEl.querySelectorAll(".float-child");
                for (var i = 0; i < fc.length; i++) {
                    var cell = fc[i];
                    var hasMap = cell.querySelector && cell.querySelector(".leaflet-container");
                    if (hasMap) {
                        cell.style.setProperty("float", "none", "important");
                        cell.style.setProperty("width", "100%", "important");
                        cell.style.setProperty("flex", "1 1 0", "important");
                        cell.style.setProperty("min-height", "0", "important");
                        cell.style.setProperty("display", "flex", "important");
                        cell.style.setProperty("flex-direction", "column", "important");
                        cell.style.setProperty("overflow", "hidden", "important");
                        var me = cell.querySelector(".leaflet-container");
                        if (me) {
                            me.style.setProperty("height", "100%", "important");
                            me.style.setProperty("max-height", "none", "important");
                            me.style.setProperty("width", "100%", "important");
                            me.style.setProperty("flex", "1 1 0", "important");
                            me.style.setProperty("min-height", "0", "important");
                        }
                    } else {
                        cell.style.setProperty("float", "none", "important");
                        cell.style.setProperty("flex-shrink", "0", "important");
                        cell.style.setProperty("flex-grow", "0", "important");
                    }
                }
            }
            var md = document.getElementById("map_div");
            if (md) {
                md.style.setProperty("height", "100%", "important");
                md.style.setProperty("max-height", "none", "important");
                md.style.setProperty("width", "100%", "important");
                md.style.setProperty("flex", "1 1 0", "important");
                md.style.setProperty("min-height", "0", "important");
            }
            var maps = document.querySelectorAll(".leaflet-container");
            for (var j = 0; j < maps.length; j++) {
                maps[j].style.setProperty("height", "100%", "important");
                maps[j].style.setProperty("max-height", "none", "important");
                maps[j].style.setProperty("width", "100%", "important");
                maps[j].style.setProperty("flex", "1 1 0", "important");
                maps[j].style.setProperty("min-height", "0", "important");
            }
            invalidateLeafletMaps();
            win.dispatchEvent(new Event("resize"));
        } catch (e1) {}
    }
    var raf = null;
    function schedule() {
        if (raf) return;
        raf = win.requestAnimationFrame(function () {
            raf = null;
            stretchLayout();
        });
    }
    win.addEventListener("resize", schedule, { passive: true });
    try {
        var pw = win.parent;
        if (pw && pw !== win) {
            pw.addEventListener("resize", schedule, { passive: true });
        }
    } catch (ePw) {}
    if (win.visualViewport) {
        win.visualViewport.addEventListener("resize", schedule, { passive: true });
    }
    if (win.ResizeObserver) {
        var ro = new win.ResizeObserver(schedule);
        ro.observe(document.documentElement);
    }
    schedule();
    win.addEventListener("load", schedule, { passive: true });
    setTimeout(schedule, 80);
    setTimeout(schedule, 400);
    setTimeout(schedule, 1200);
})();
{% endraw %}
{% endmacro %}
"""
)


class _StreamlitFoliumResizeBridge(MacroElement):
    _template = _STREAMLIT_FOLIUM_RESIZE_MACRO


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


def _pick_zoom_to_action(map_actions: list) -> dict | None:
    focus_i = st.session_state.get(SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW)
    gs = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
    rows = gs.get("feature_rows") if isinstance(gs, dict) else None
    if (
        focus_i is not None
        and isinstance(focus_i, int)
        and isinstance(rows, list)
        and 0 <= focus_i < len(rows)
    ):
        for action in map_actions:
            if action.get("type") == "zoomTo":
                return action
        return None
    for idx in range(len(map_actions) - 1, -1, -1):
        if map_actions[idx].get("type") == "zoomTo":
            return map_actions[idx]
    return None


def _compute_center_and_zoom(map_actions: list) -> tuple[list[float], int]:
    center = [42.34, -88.0]
    zoom_start = 10

    zoom_action = _pick_zoom_to_action(map_actions)
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


def merge_persist_basemap_into_actions(
    incoming: list | None,
    previous_full: list | None,
) -> list:
    if not incoming:
        return incoming or []
    out = list(incoming)
    if any(a.get("type") == "setBasemap" for a in out):
        return out
    prev_bid = None
    if previous_full:
        for a in reversed(previous_full):
            if a.get("type") == "setBasemap" and a.get("basemap_id"):
                prev_bid = a["basemap_id"]
                break
    if prev_bid:
        out.append({"type": "setBasemap", "basemap_id": prev_bid})
    return out


def _basemap_id_from_actions(map_actions: list) -> str:
    for a in reversed(map_actions):
        if a.get("type") == "setBasemap":
            raw = a.get("basemap_id")
            if isinstance(raw, str) and raw.strip():
                return validate_basemap_id(raw.strip())
    return GEO_BASEMAP_DEFAULT_ID


def active_basemap_id_from_map_actions(map_actions: list | None) -> str:
    if not map_actions:
        return GEO_BASEMAP_DEFAULT_ID
    return _basemap_id_from_actions(map_actions)


def _folium_map_with_basemap(
    center: list[float],
    zoom_start: int,
    basemap_id: str,
    map_width: int | str,
    height: int,
) -> folium.Map:
    bid = basemap_id if basemap_id in GEO_BASEMAP_SPECS else GEO_BASEMAP_DEFAULT_ID
    tiles_kw, url, attr = GEO_BASEMAP_SPECS[bid]
    if url:
        m = folium.Map(
            location=center,
            zoom_start=zoom_start,
            tiles=None,
            width=map_width,
            height=height,
        )
        folium.TileLayer(tiles=url, attr=attr or "", name="Basemap").add_to(m)
    else:
        m = folium.Map(
            location=center,
            zoom_start=zoom_start,
            tiles=tiles_kw,
            width=map_width,
            height=height,
        )
    return m


def render_geo_map(map_actions, width: int | str | None = 700, height=400):
    if not map_actions:
        return None

    map_width: int | str = "100%" if width is None else width

    center, zoom_start = _compute_center_and_zoom(map_actions)
    basemap_id = _basemap_id_from_actions(map_actions)
    m = _folium_map_with_basemap(center, zoom_start, basemap_id, map_width, height)

    zoom_action = _pick_zoom_to_action(map_actions)
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

        if action_type == "setBasemap":
            continue

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
    _StreamlitFoliumResizeBridge().add_to(m)
    return m
