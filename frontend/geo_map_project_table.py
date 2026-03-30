import html

import streamlit as st

from constants import (
    GEO_MAP_TABLE_GOTO_BUTTON_BG,
    GEO_MAP_TABLE_GOTO_BUTTON_FONT_SIZE_PX,
    GEO_MAP_TABLE_GOTO_BUTTON_HOVER,
    GEO_MAP_TABLE_GOTO_BUTTON_MIN_HEIGHT_PX,
    GEO_MAP_TABLE_GOTO_BUTTON_MIN_WIDTH,
    GEO_MAP_TABLE_GOTO_BUTTON_PADDING,
    GEO_MAP_TABLE_HEADER_GAP_PX,
    GEO_MAP_TABLE_HEADER_PADDING_X_PX,
    GEO_MAP_TABLE_HEADER_PADDING_Y_PX,
    GEO_MAP_TABLE_NAME_CELL_STYLE,
    GEO_MAP_TABLE_NAME_DOM_MAX_CHARS,
    GEO_MAP_TABLE_ROW_ACTION_GAP_PX,
    GEO_MAP_TABLE_ROW_LINE_HEIGHT,
    GEO_MAP_TABLE_ROW_PADDING_X_PX,
    GEO_MAP_TABLE_ROW_PADDING_Y_PX,
    SESSION_KEY_GEO_MAP_TABLE_EXPANDED,
    SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW,
    SESSION_KEY_GEO_RESULT_SUMMARY,
    SESSION_KEY_MAP_ACTIONS,
    build_geo_map_panel_result_rows_css,
)

_TOGGLE_CSS = """
[class*="st-key-geo_tbl_toggle_wrap"] {
    padding: 0 !important;
    margin: 0 !important;
}
[class*="st-key-geo_tbl_toggle_wrap"] > div {
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}
[class*="st-key-geo_tbl_toggle_wrap"] [data-testid="stVerticalBlock"] {
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}
[class*="st-key-geo_map_tbl_exp"],
[class*="st-key-geo_map_tbl_col"] {
    padding: 0 !important;
    margin: 0 !important;
    width: 100% !important;
}
[class*="st-key-geo_map_tbl_exp"] button,
[class*="st-key-geo_map_tbl_col"] button {
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding: 0.3rem 0.7rem !important;
    min-height: 0 !important;
    height: auto !important;
    line-height: 1.4 !important;
    font-size: 0.82rem !important;
    background: rgba(49,51,63,0.04) !important;
    border: 1px solid rgba(49,51,63,0.18) !important;
    border-radius: 6px !important;
    color: rgba(49,51,63,0.75) !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
    transition: background 0.15s !important;
}
[class*="st-key-geo_map_tbl_exp"] button:hover,
[class*="st-key-geo_map_tbl_col"] button:hover {
    background: rgba(49,51,63,0.09) !important;
}
[class*="st-key-geo_map_tbl_exp"] button p,
[class*="st-key-geo_map_tbl_col"] button p {
    flex: 1 1 auto !important;
    text-align: left !important;
    margin: 0 !important;
}
[class*="st-key-geo_map_tbl_exp"] button svg,
[class*="st-key-geo_map_tbl_col"] button svg,
[class*="st-key-geo_map_tbl_exp"] button [data-testid="baseButton-icon"],
[class*="st-key-geo_map_tbl_col"] button [data-testid="baseButton-icon"] {
    display: none !important;
}
[class*="st-key-geo_map_tbl_exp"] button::after {
    content: "▼";
    flex-shrink: 0 !important;
    font-size: 0.7rem !important;
    opacity: 0.5 !important;
    margin-left: auto !important;
}
[class*="st-key-geo_map_tbl_col"] button::after {
    content: "▶";
    flex-shrink: 0 !important;
    font-size: 0.7rem !important;
    opacity: 0.5 !important;
    margin-left: auto !important;
}
"""


def geo_map_project_table_css_rules() -> str:
    goto_bg = GEO_MAP_TABLE_GOTO_BUTTON_BG
    goto_hov = GEO_MAP_TABLE_GOTO_BUTTON_HOVER
    goto_pad = GEO_MAP_TABLE_GOTO_BUTTON_PADDING
    goto_min = GEO_MAP_TABLE_GOTO_BUTTON_MIN_WIDTH
    goto_mnh = GEO_MAP_TABLE_GOTO_BUTTON_MIN_HEIGHT_PX
    goto_fs = GEO_MAP_TABLE_GOTO_BUTTON_FONT_SIZE_PX
    rpy = GEO_MAP_TABLE_ROW_PADDING_Y_PX
    rpx = GEO_MAP_TABLE_ROW_PADDING_X_PX
    rag = GEO_MAP_TABLE_ROW_ACTION_GAP_PX
    rlh = GEO_MAP_TABLE_ROW_LINE_HEIGHT
    return _TOGGLE_CSS.strip() + f"""
[class*="st-key-geo_tbl_rows"] [data-testid="stVerticalBlock"] {{
    gap: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stVerticalBlock"] > div {{
    flex-shrink: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] {{
    padding: {rpy}px {rpx}px !important;
    border-bottom: 1px solid rgba(49,51,63,0.08) !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
    width: 100% !important;
    flex-shrink: 0 !important;
    box-sizing: border-box !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"]:last-child {{
    border-bottom: none !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 0 !important;
    padding: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stMarkdownContainer"] {{
    margin: 0 !important;
    padding: 0 !important;
    margin-bottom: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stMarkdownContainer"] p {{
    margin: 0 !important;
    padding: 0 !important;
    line-height: {rlh} !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {{
    min-width: 0 !important;
    overflow: hidden !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) [data-testid="stMarkdownContainer"] p {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    max-width: 100% !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
    flex: 0 0 auto !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    padding-left: {rag}px !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child > [data-testid="stVerticalBlock"] {{
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    min-height: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child [data-testid="stElementContainer"] {{
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}}
[class*="st-key-geo_map_goto_"] button {{
    padding: {goto_pad} !important;
    min-width: {goto_min} !important;
    min-height: {goto_mnh}px !important;
    height: auto !important;
    max-height: none !important;
    background-color: {goto_bg} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 4px !important;
    font-size: {goto_fs}px !important;
    line-height: 1.2 !important;
    white-space: nowrap !important;
    box-sizing: border-box !important;
}}
[class*="st-key-geo_map_goto_"] button p {{
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.2 !important;
    font-size: inherit !important;
}}
[class*="st-key-geo_map_goto_"] button:hover {{
    background-color: {goto_hov} !important;
}}
[class*="st-key-geo_map_goto_"] button:disabled {{
    background-color: rgba(49,51,63,0.15) !important;
    color: rgba(49,51,63,0.4) !important;
}}
"""


def _norm_id(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


_GEO_LOOKUP_ACTION_TYPES = frozenset({
    "addFeatureLayer",
    "addProjectGeometryLayer",
    "addProjectRepPointsLayer",
})


def _build_geometry_lookups(map_actions: list) -> tuple[dict, dict]:
    by_pid: dict = {}
    by_oid: dict = {}
    for action in map_actions:
        if action.get("type") not in _GEO_LOOKUP_ACTION_TYPES:
            continue
        fc = action.get("geojson")
        if not isinstance(fc, dict) or fc.get("type") != "FeatureCollection":
            continue
        for feat in fc.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            props = feat.get("properties") or {}
            pid = props.get("project_id")
            if pid is not None:
                by_pid[_norm_id(pid)] = geom
            raw_oid = props.get("OBJECTID")
            if raw_oid is None:
                raw_oid = props.get("objectid")
            if raw_oid is not None:
                by_oid[_norm_id(raw_oid)] = geom
    return by_pid, by_oid


def _geometry_for_feature_row(row: dict, by_pid: dict, by_oid: dict):
    pid = _norm_id(row.get("project_id"))
    if pid is not None and pid in by_pid:
        return by_pid[pid]
    oid = _norm_id(row.get("OBJECTID"))
    if oid is None:
        oid = _norm_id(row.get("objectid"))
    if oid is not None and oid in by_oid:
        return by_oid[oid]
    return None


def _zoom_action_for_geometry(geom: dict) -> dict:
    return {
        "type": "zoomTo",
        "geometry": {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": geom, "properties": {}}],
        },
    }


def prepend_focus_zoom_if_any(
    augmented_actions: list,
    map_actions_base: list,
    geo_summary: dict | None,
) -> list:
    focus_i = st.session_state.get(SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW)
    if focus_i is None or not isinstance(geo_summary, dict):
        return augmented_actions
    rows = geo_summary.get("feature_rows") or []
    if not isinstance(focus_i, int) or focus_i < 0 or focus_i >= len(rows):
        st.session_state[SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW] = None
        return augmented_actions
    by_pid, by_oid = _build_geometry_lookups(map_actions_base)
    geom = _geometry_for_feature_row(rows[focus_i], by_pid, by_oid)
    if not geom:
        return augmented_actions
    out = list(augmented_actions)
    out.insert(0, _zoom_action_for_geometry(geom))
    return out


def _get_row_name(row: dict) -> str:
    for nk in ("Name", "name", "PROJECT_NAME", "Project_Name", "Title", "title"):
        nv = row.get(nk)
        if nv is not None and str(nv).strip():
            return str(nv)
    pid = row.get("project_id")
    if pid is not None:
        return str(pid)
    return "\u2014"


def _cell_name_text(full_name: str) -> str:
    t = " ".join(((full_name or "").strip()).split())
    if not t:
        return "\u2014"
    mx = GEO_MAP_TABLE_NAME_DOM_MAX_CHARS
    if len(t) <= mx:
        return t
    return t[: mx - 1] + "\u2026"


@st.fragment
def render_geo_map_bottom_table() -> None:
    geo_summary = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
    if not isinstance(geo_summary, dict):
        return
    rows = geo_summary.get("feature_rows") or []
    total = geo_summary.get("total", 0)
    if total <= 0 or not rows:
        return

    map_actions = st.session_state.get(SESSION_KEY_MAP_ACTIONS, [])
    by_pid, by_oid = _build_geometry_lookups(map_actions)
    expanded = st.session_state.get(SESSION_KEY_GEO_MAP_TABLE_EXPANDED, True)
    label_plural = geo_summary.get("label_plural", "results")

    _panel_rules = (
        build_geo_map_panel_result_rows_css(expanded)
        .replace("<style>", "")
        .replace("</style>", "")
        .strip()
    )
    _tbl_rules = geo_map_project_table_css_rules()
    st.markdown(
        f"<style>\n{_panel_rules}\n{_tbl_rules}\n</style>",
        unsafe_allow_html=True,
    )

    btn_key = "geo_map_tbl_exp" if expanded else "geo_map_tbl_col"

    with st.container(key="geo_tbl_toggle_wrap"):
        if st.button(f"{total} {label_plural}", key=btn_key, use_container_width=True):
            st.session_state[SESSION_KEY_GEO_MAP_TABLE_EXPANDED] = not expanded
            st.rerun(scope="fragment")

    if expanded:
        hpy = GEO_MAP_TABLE_HEADER_PADDING_Y_PX
        hpx = GEO_MAP_TABLE_HEADER_PADDING_X_PX
        hg = GEO_MAP_TABLE_HEADER_GAP_PX
        lh = GEO_MAP_TABLE_ROW_LINE_HEIGHT
        st.markdown(
            f'<div style="display:flex;flex-direction:row;align-items:center;'
            f"padding:{hpy}px {hpx}px;gap:{hg}px;"
            "background:rgba(49,51,63,0.06);border-bottom:1px solid rgba(49,51,63,0.12);"
            "font-size:0.72rem;font-weight:600;text-transform:uppercase;"
            'letter-spacing:0.04em;color:rgba(49,51,63,0.55);">'
            '<span style="flex:0 0 10%">ID</span>'
            '<span style="flex:1 1 auto;min-width:0">Name</span>'
            '<span style="flex:0 0 auto;min-width:4.75rem"></span>'
            "</div>",
            unsafe_allow_html=True,
        )

        with st.container(key="geo_tbl_rows", height=200, border=False):
            for i, row in enumerate(rows):
                pid = row.get("project_id")
                raw_oid = row.get("OBJECTID")
                if raw_oid is None:
                    raw_oid = row.get("objectid")
                display_id = pid if pid is not None else (raw_oid if raw_oid is not None else "\u2014")
                name = _get_row_name(row)
                has_geom = _geometry_for_feature_row(row, by_pid, by_oid) is not None

                r1, r2, r3 = st.columns([10, 58, 14])
                with r1:
                    st.markdown(
                        f'<p style="margin:0;padding:0;font-size:0.78rem;'
                        f'color:rgba(49,51,63,0.55);line-height:{lh};white-space:nowrap">'
                        f"{html.escape(str(display_id))}</p>",
                        unsafe_allow_html=True,
                    )
                with r2:
                    st.markdown(
                        f'<p style="{GEO_MAP_TABLE_NAME_CELL_STYLE}">'
                        f"{html.escape(_cell_name_text(str(name)))}</p>",
                        unsafe_allow_html=True,
                    )
                with r3:
                    if st.button(
                        "Go to",
                        key=f"geo_map_goto_{i}",
                        use_container_width=False,
                        disabled=not has_geom,
                    ):
                        st.session_state[SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW] = i
                        st.rerun()
