import html

import streamlit as st
from geo_feature_display import (
    geo_feature_row_display_id,
    geo_feature_row_display_label,
)

from constants import (
    GEO_MAP_STREAMLIT_KEY_TABLE_FLYOUT,
    GEO_MAP_TABLE_DIVIDER_DARK,
    GEO_MAP_TABLE_DIVIDER_LIGHT,
    GEO_MAP_TABLE_FG_BODY_DARK,
    GEO_MAP_TABLE_FG_BODY_LIGHT,
    GEO_MAP_TABLE_FG_MUTED_DARK,
    GEO_MAP_TABLE_FG_MUTED_LIGHT,
    GEO_MAP_TABLE_FLYOUT_MAX_HEIGHT_CSS,
    GEO_MAP_TABLE_FLYOUT_Z_INDEX,
    GEO_MAP_TABLE_GOTO_BUTTON_BG,
    GEO_MAP_TABLE_GOTO_BUTTON_FONT_SIZE_PX,
    GEO_MAP_TABLE_GOTO_BUTTON_HEIGHT_PX,
    GEO_MAP_TABLE_GOTO_BUTTON_HOVER,
    GEO_MAP_TABLE_GOTO_BUTTON_PAD_X_PX,
    GEO_MAP_TABLE_GOTO_BUTTON_SHRINK_PCT,
    GEO_MAP_TABLE_GOTO_DISABLED_BG_DARK,
    GEO_MAP_TABLE_GOTO_DISABLED_BG_LIGHT,
    GEO_MAP_TABLE_GOTO_DISABLED_FG_DARK,
    GEO_MAP_TABLE_GOTO_DISABLED_FG_LIGHT,
    GEO_MAP_TABLE_HEAD_BG_DARK,
    GEO_MAP_TABLE_HEAD_BG_LIGHT,
    GEO_MAP_TABLE_HEAD_RULE_DARK,
    GEO_MAP_TABLE_HEAD_RULE_LIGHT,
    GEO_MAP_TABLE_HEADER_GAP_PX,
    GEO_MAP_TABLE_HEADER_PADDING_X_PX,
    GEO_MAP_TABLE_HEADER_PADDING_Y_PX,
    GEO_MAP_TABLE_NAME_CELL_STYLE,
    GEO_MAP_TABLE_NAME_DOM_MAX_CHARS,
    GEO_MAP_TABLE_NAME_FONT_SIZE_REM,
    GEO_MAP_TABLE_ROW_LINE_HEIGHT,
    GEO_MAP_TABLE_ROW_PADDING_LEFT_PX,
    GEO_MAP_TABLE_ROW_PADDING_RIGHT_PX,
    GEO_MAP_TABLE_ROW_PADDING_Y_PX,
    GEO_MAP_TABLE_SCROLL_VISIBLE_ROW_COUNT,
    GEO_MAP_TABLE_TOGGLE_BG_DARK,
    GEO_MAP_TABLE_TOGGLE_BG_LIGHT,
    GEO_MAP_TABLE_TOGGLE_BORDER_DARK,
    GEO_MAP_TABLE_TOGGLE_BORDER_LIGHT,
    GEO_MAP_TABLE_TOGGLE_FG_DARK,
    GEO_MAP_TABLE_TOGGLE_FG_LIGHT,
    GEO_MAP_TABLE_TOGGLE_HOVER_BG_DARK,
    GEO_MAP_TABLE_TOGGLE_HOVER_BG_LIGHT,
    SESSION_KEY_GEO_MAP_TABLE_EXPANDED,
    SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW,
    SESSION_KEY_GEO_RESULT_SUMMARY,
    SESSION_KEY_MAP_ACTIONS,
    build_geo_map_panel_result_rows_css,
)


def geo_map_project_table_css_rules() -> str:
    goto_bg = GEO_MAP_TABLE_GOTO_BUTTON_BG
    goto_hov = GEO_MAP_TABLE_GOTO_BUTTON_HOVER
    goto_h = GEO_MAP_TABLE_GOTO_BUTTON_HEIGHT_PX
    goto_px = GEO_MAP_TABLE_GOTO_BUTTON_PAD_X_PX
    goto_fs = GEO_MAP_TABLE_GOTO_BUTTON_FONT_SIZE_PX
    goto_shrink_pct = GEO_MAP_TABLE_GOTO_BUTTON_SHRINK_PCT
    rpy = GEO_MAP_TABLE_ROW_PADDING_Y_PX
    rlh = GEO_MAP_TABLE_ROW_LINE_HEIGHT
    hpy = GEO_MAP_TABLE_HEADER_PADDING_Y_PX
    hpx = GEO_MAP_TABLE_HEADER_PADDING_X_PX
    hg = GEO_MAP_TABLE_HEADER_GAP_PX
    fml = GEO_MAP_TABLE_FG_MUTED_LIGHT
    fmd = GEO_MAP_TABLE_FG_MUTED_DARK
    fbl = GEO_MAP_TABLE_FG_BODY_LIGHT
    fbd = GEO_MAP_TABLE_FG_BODY_DARK
    tfgl = GEO_MAP_TABLE_TOGGLE_FG_LIGHT
    tfgd = GEO_MAP_TABLE_TOGGLE_FG_DARK
    tbgl = GEO_MAP_TABLE_TOGGLE_BG_LIGHT
    tbgd = GEO_MAP_TABLE_TOGGLE_BG_DARK
    tbdl = GEO_MAP_TABLE_TOGGLE_BORDER_LIGHT
    tbdd = GEO_MAP_TABLE_TOGGLE_BORDER_DARK
    thbl = GEO_MAP_TABLE_TOGGLE_HOVER_BG_LIGHT
    thbd = GEO_MAP_TABLE_TOGGLE_HOVER_BG_DARK
    divl = GEO_MAP_TABLE_DIVIDER_LIGHT
    divd = GEO_MAP_TABLE_DIVIDER_DARK
    hbg_l = GEO_MAP_TABLE_HEAD_BG_LIGHT
    hbg_d = GEO_MAP_TABLE_HEAD_BG_DARK
    hrl_l = GEO_MAP_TABLE_HEAD_RULE_LIGHT
    hrl_d = GEO_MAP_TABLE_HEAD_RULE_DARK
    gdb_l = GEO_MAP_TABLE_GOTO_DISABLED_BG_LIGHT
    gdb_d = GEO_MAP_TABLE_GOTO_DISABLED_BG_DARK
    gdf_l = GEO_MAP_TABLE_GOTO_DISABLED_FG_LIGHT
    gdf_d = GEO_MAP_TABLE_GOTO_DISABLED_FG_DARK
    rpx_left = GEO_MAP_TABLE_ROW_PADDING_LEFT_PX
    rpx_right = GEO_MAP_TABLE_ROW_PADDING_RIGHT_PX
    name_fs = GEO_MAP_TABLE_NAME_FONT_SIZE_REM
    fly_mh = GEO_MAP_TABLE_FLYOUT_MAX_HEIGHT_CSS
    fly_z = GEO_MAP_TABLE_FLYOUT_Z_INDEX
    scroll_n = GEO_MAP_TABLE_SCROLL_VISIBLE_ROW_COUNT
    tbl_body_scroll_max_px = scroll_n * (
        2 * GEO_MAP_TABLE_ROW_PADDING_Y_PX
        + GEO_MAP_TABLE_GOTO_BUTTON_HEIGHT_PX
        + 4
    ) + max(0, scroll_n - 1)
    tbl_hdr_min_px = max(hpy * 2 + 14, 40)
    dbg_u = '[class*="geo_map_table_debug_wrap"]'
    dbg_k = '[class*="geo-map-table-debug-wrap"]'
    sel_dbg = f"{dbg_u}, {dbg_k}"
    fly_u = '[class*="geo_map_table_flyout"]'
    fly_k = '[class*="geo-map-table-flyout"]'
    sel_fly = f"{fly_u}, {fly_k}"
    sel_hdr = f"{dbg_u} .geo-map-tbl-header, {dbg_k} .geo-map-tbl-header"
    sel_vb_chain = (
        f'{dbg_u} > div > [data-testid="stVerticalBlock"], '
        f'{dbg_k} > div > [data-testid="stVerticalBlock"], '
        f'{dbg_u} > div > div > [data-testid="stVerticalBlock"], '
        f'{dbg_k} > div > div > [data-testid="stVerticalBlock"]'
    )
    sel_fly_row = (
        f'{dbg_u} [data-testid="stVerticalBlock"] > div:has({fly_u}), '
        f'{dbg_k} [data-testid="stVerticalBlock"] > div:has({fly_u}), '
        f'{dbg_u} [data-testid="stVerticalBlock"] > div:has({fly_k}), '
        f'{dbg_k} [data-testid="stVerticalBlock"] > div:has({fly_k})'
    )
    sel_fly_vb = (
        f'{fly_u} [data-testid="stVerticalBlock"]:not([class*="st-key-geo_tbl_rows"]), '
        f'{fly_k} [data-testid="stVerticalBlock"]:not([class*="st-key-geo_tbl_rows"])'
    )
    sel_fly_hdr_ec = (
        f'{fly_u} [data-testid="stElementContainer"]:has(.geo-map-tbl-header), '
        f'{fly_k} [data-testid="stElementContainer"]:has(.geo-map-tbl-header)'
    )
    sel_fly_hdr_md = (
        f'{fly_u} [data-testid="stMarkdownContainer"]:has(.geo-map-tbl-header), '
        f'{fly_k} [data-testid="stMarkdownContainer"]:has(.geo-map-tbl-header)'
    )
    sel_toggle_row = (
        f'{dbg_u} [data-testid="stVerticalBlock"] > div:has([class*="geo_tbl_toggle_wrap"]), '
        f'{dbg_k} [data-testid="stVerticalBlock"] > div:has([class*="geo_tbl_toggle_wrap"])'
    )
    sel_toggle_ec = (
        f'{dbg_u} [data-testid="stVerticalBlock"] > div:has([class*="geo_tbl_toggle_wrap"]) '
        f'[data-testid="stElementContainer"], '
        f'{dbg_k} [data-testid="stVerticalBlock"] > div:has([class*="geo_tbl_toggle_wrap"]) '
        f'[data-testid="stElementContainer"]'
    )
    return f"""
[class*="st-key-geo_tbl_toggle_wrap"] {{
    padding: 0 !important;
    margin: 0 !important;
}}
[class*="st-key-geo_tbl_toggle_wrap"] > div {{
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}}
[class*="st-key-geo_tbl_toggle_wrap"] [data-testid="stVerticalBlock"] {{
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}}
[class*="st-key-geo_map_tbl_exp"],
[class*="st-key-geo_map_tbl_col"] {{
    padding: 0 !important;
    margin: 0 !important;
    width: 100% !important;
}}
[class*="st-key-geo_map_tbl_exp"] button,
[class*="st-key-geo_map_tbl_col"] button {{
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding: 0.3rem 0.7rem !important;
    min-height: 0 !important;
    height: auto !important;
    line-height: 1.4 !important;
    font-size: 0.82rem !important;
    background: {tbgl} !important;
    border: 1px solid {tbdl} !important;
    border-radius: 6px !important;
    color: {tfgl} !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
    transition: background 0.15s !important;
}}
[class*="st-key-geo_map_tbl_exp"] button:hover,
[class*="st-key-geo_map_tbl_col"] button:hover {{
    background: {thbl} !important;
}}
@media (prefers-color-scheme: dark) {{
    [class*="st-key-geo_map_tbl_exp"] button,
    [class*="st-key-geo_map_tbl_col"] button {{
        background: {tbgd} !important;
        border-color: {tbdd} !important;
        color: {tfgd} !important;
    }}
    [class*="st-key-geo_map_tbl_exp"] button:hover,
    [class*="st-key-geo_map_tbl_col"] button:hover {{
        background: {thbd} !important;
    }}
}}
@supports (background-color: light-dark(white, black)) {{
    [class*="st-key-geo_map_tbl_exp"] button,
    [class*="st-key-geo_map_tbl_col"] button {{
        background: light-dark({tbgl}, {tbgd}) !important;
        border-color: light-dark({tbdl}, {tbdd}) !important;
        color: light-dark({tfgl}, {tfgd}) !important;
    }}
    [class*="st-key-geo_map_tbl_exp"] button:hover,
    [class*="st-key-geo_map_tbl_col"] button:hover {{
        background: light-dark({thbl}, {thbd}) !important;
    }}
}}
[class*="st-key-geo_map_tbl_exp"] button p,
[class*="st-key-geo_map_tbl_col"] button p {{
    flex: 1 1 auto !important;
    text-align: left !important;
    margin: 0 !important;
}}
[class*="st-key-geo_map_tbl_exp"] button svg,
[class*="st-key-geo_map_tbl_col"] button svg,
[class*="st-key-geo_map_tbl_exp"] button [data-testid="baseButton-icon"],
[class*="st-key-geo_map_tbl_col"] button [data-testid="baseButton-icon"] {{
    display: none !important;
}}
[class*="st-key-geo_map_tbl_exp"] button::after {{
    content: "▼";
    flex-shrink: 0 !important;
    font-size: 0.7rem !important;
    opacity: 0.5 !important;
    margin-left: auto !important;
}}
[class*="st-key-geo_map_tbl_col"] button::after {{
    content: "▶";
    flex-shrink: 0 !important;
    font-size: 0.7rem !important;
    opacity: 0.5 !important;
    margin-left: auto !important;
}}
{sel_hdr} {{
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    padding: {hpy}px {hpx}px !important;
    gap: {hg}px !important;
    min-height: {tbl_hdr_min_px}px !important;
    background: {hbg_l} !important;
    border-bottom: 1px solid {hrl_l} !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    color: {fml} !important;
    box-sizing: border-box !important;
}}
@media (prefers-color-scheme: dark) {{
    {sel_hdr} {{
        background: {hbg_d} !important;
        border-bottom-color: {hrl_d} !important;
        color: {fmd} !important;
    }}
}}
@supports (color: light-dark(white, black)) {{
    {sel_hdr} {{
        background: light-dark({hbg_l}, {hbg_d}) !important;
        border-bottom-color: light-dark({hrl_l}, {hrl_d}) !important;
        color: light-dark({fml}, {fmd}) !important;
    }}
}}
[class*="st-key-geo_tbl_rows"] .geo-map-tbl-id {{
    color: {fml} !important;
}}
[class*="st-key-geo_tbl_rows"] .geo-map-tbl-name {{
    color: {fbl} !important;
}}
@media (prefers-color-scheme: dark) {{
    [class*="st-key-geo_tbl_rows"] .geo-map-tbl-id {{
        color: {fmd} !important;
    }}
    [class*="st-key-geo_tbl_rows"] .geo-map-tbl-name {{
        color: {fbd} !important;
    }}
}}
@supports (color: light-dark(white, black)) {{
    [class*="st-key-geo_tbl_rows"] .geo-map-tbl-id {{
        color: light-dark({fml}, {fmd}) !important;
    }}
    [class*="st-key-geo_tbl_rows"] .geo-map-tbl-name {{
        color: light-dark({fbl}, {fbd}) !important;
    }}
}}
[data-testid="stVerticalBlock"][class*="st-key-geo_map_table_flyout"],
[data-testid="stVerticalBlock"][class*="st-key-geo-map-table-flyout"] {{
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
    min-height: 0 !important;
    flex-shrink: 1 !important;
    max-width: 100% !important;
}}
[data-testid="stVerticalBlock"][class*="st-key-geo_tbl_rows"] {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    max-height: {tbl_body_scroll_max_px}px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scrollbar-width: thin !important;
    -webkit-overflow-scrolling: touch !important;
}}
[data-testid="stVerticalBlock"][class*="st-key-geo_tbl_rows"]::-webkit-scrollbar {{
    width: 8px !important;
}}
[data-testid="stVerticalBlock"][class*="st-key-geo_tbl_rows"]::-webkit-scrollbar-thumb {{
    background: rgba(49, 51, 63, 0.35) !important;
    border-radius: 4px !important;
}}
@media (prefers-color-scheme: dark) {{
    [data-testid="stVerticalBlock"][class*="st-key-geo_tbl_rows"]::-webkit-scrollbar-thumb {{
        background: rgba(232, 234, 237, 0.35) !important;
    }}
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stVerticalBlock"] {{
    gap: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stVerticalBlock"] > div {{
    flex-shrink: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] {{
    padding: {rpy}px {rpx_right}px {rpy}px {rpx_left}px !important;
    border-bottom: 1px solid {divl} !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
    width: 100% !important;
    flex-shrink: 0 !important;
    box-sizing: border-box !important;
    gap: 0 !important;
    column-gap: 0 !important;
    justify-content: flex-start !important;
}}
@media (prefers-color-scheme: dark) {{
    [class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] {{
        border-bottom-color: {divd} !important;
    }}
}}
@supports (border-color: light-dark(white, black)) {{
    [class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] {{
        border-bottom-color: light-dark({divl}, {divd}) !important;
    }}
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"]:last-child {{
    border-bottom: none !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    padding: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:first-child) {{
    min-width: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{
    flex: 0 0 10% !important;
    min-width: 2.75rem !important;
    max-width: 14% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
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
    flex: 1 1 0% !important;
    min-width: 0 !important;
    overflow: hidden !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) [data-testid="stMarkdownContainer"] p {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    max-width: 100% !important;
    font-size: {name_fs} !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
    flex: 0 0 auto !important;
    display: flex !important;
    align-items: center !important;
    padding: 0 !important;
}}
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child > [data-testid="stVerticalBlock"],
[class*="st-key-geo_tbl_rows"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child [data-testid="stElementContainer"] {{
    margin: 0 !important;
    padding: 0 !important;
    min-height: 0 !important;
    width: 100% !important;
}}
[class*="st-key-geo_map_goto_"] .stButton,
[class*="st-key-geo_map_goto_"] [data-testid="stElementContainer"] .stButton {{
    width: calc(100% - {goto_shrink_pct}%) !important;
    max-width: calc(100% - {goto_shrink_pct}%) !important;
    height: {goto_h}px !important;
    max-height: {goto_h}px !important;
    min-height: 0 !important;
    margin-left: auto !important;
    margin-right: 0 !important;
    box-sizing: border-box !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
[class*="st-key-geo_map_goto_"] [data-baseweb="button"],
[class*="st-key-geo_map_goto_"] .stButton > button,
[class*="st-key-geo_map_goto_"] button[data-baseweb="button"],
[class*="st-key-geo_map_goto_"] button {{
    width: 100% !important;
    height: {goto_h}px !important;
    min-height: {goto_h}px !important;
    max-height: {goto_h}px !important;
    padding: 0 {goto_px}px !important;
    margin: 0 !important;
    background-color: {goto_bg} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 4px !important;
    font-size: {goto_fs}px !important;
    white-space: nowrap !important;
    box-sizing: border-box !important;
    align-self: center !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
[class*="st-key-geo_map_goto_"] button p {{
    margin: 0 !important;
    padding: 0 !important;
    font-size: inherit !important;
    line-height: 1 !important;
}}
[class*="st-key-geo_map_goto_"] button:hover {{
    background-color: {goto_hov} !important;
}}
[class*="st-key-geo_map_goto_"] button:disabled {{
    background-color: {gdb_l} !important;
    color: {gdf_l} !important;
}}
@media (prefers-color-scheme: dark) {{
    [class*="st-key-geo_map_goto_"] button:disabled {{
        background-color: {gdb_d} !important;
        color: {gdf_d} !important;
    }}
}}
@supports (background-color: light-dark(white, black)) {{
    [class*="st-key-geo_map_goto_"] button:disabled {{
        background-color: light-dark({gdb_l}, {gdb_d}) !important;
        color: light-dark({gdf_l}, {gdf_d}) !important;
    }}
}}
{sel_vb_chain} {{
    gap: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    justify-content: flex-start !important;
    align-content: flex-start !important;
}}
{sel_dbg} {{
    position: relative !important;
    overflow: visible !important;
    z-index: {fly_z - 5} !important;
}}
{sel_fly_row} {{
    flex: 0 0 0 !important;
    min-height: 0 !important;
    height: 0 !important;
    max-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
    position: relative !important;
}}
{sel_fly} {{
    position: absolute !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 100% !important;
    top: auto !important;
    width: 100% !important;
    max-width: 100% !important;
    min-height: min-content !important;
    height: auto !important;
    max-height: {fly_mh} !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    z-index: {fly_z} !important;
    background-color: rgba(255, 255, 255, 0.98) !important;
    box-shadow: 0 -10px 32px rgba(0, 0, 0, 0.14) !important;
    border: 1px solid rgba(49, 51, 63, 0.18) !important;
    border-radius: 10px 10px 0 0 !important;
    box-sizing: border-box !important;
}}
@media (prefers-color-scheme: dark) {{
    {sel_fly} {{
        background-color: rgba(14, 17, 23, 0.98) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
    }}
}}
{sel_fly_vb} {{
    min-height: min-content !important;
    height: auto !important;
    gap: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}}
{fly_u} [data-testid="stVerticalBlock"] > div,
{fly_k} [data-testid="stVerticalBlock"] > div {{
    margin: 0 !important;
    padding: 0 !important;
}}
{sel_fly_hdr_ec} {{
    flex-shrink: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}}
{sel_fly_hdr_md} {{
    min-height: {tbl_hdr_min_px}px !important;
    overflow: visible !important;
    margin: 0 !important;
    padding: 0 !important;
}}
{sel_toggle_row} {{
    margin: 0 !important;
    padding: 0 !important;
    min-height: 0 !important;
}}
{sel_toggle_ec} {{
    margin: 0 !important;
    padding: 0 !important;
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
    label = geo_feature_row_display_label(row)
    if label != "\u2014":
        return label
    rid = geo_feature_row_display_id(row)
    if rid != "\u2014":
        return str(rid).strip()
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

    if expanded:
        with st.container(key=GEO_MAP_STREAMLIT_KEY_TABLE_FLYOUT):
            lh = GEO_MAP_TABLE_ROW_LINE_HEIGHT
            st.markdown(
                '<div class="geo-map-tbl-header">'
                '<span style="flex:0 0 10%">ID</span>'
                '<span style="flex:1 1 auto;min-width:0">Name</span>'
                '<span style="flex:0 0 auto;min-width:4.75rem"></span>'
                "</div>",
                unsafe_allow_html=True,
            )

            with st.container(key="geo_tbl_rows", border=False):
                for i, row in enumerate(rows):
                    display_id = geo_feature_row_display_id(row)
                    name = _get_row_name(row)
                    has_geom = _geometry_for_feature_row(row, by_pid, by_oid) is not None

                    r1, r2, r3 = st.columns([10, 58, 14], gap="small", vertical_alignment="center")
                    with r1:
                        st.markdown(
                            '<p class="geo-map-tbl-id" style="margin:0;padding:0;font-size:0.78rem;'
                            f'line-height:{lh};white-space:nowrap">'
                            + html.escape(str(display_id))
                            + "</p>",
                            unsafe_allow_html=True,
                        )
                    with r2:
                        st.markdown(
                            f'<p class="geo-map-tbl-name" style="{GEO_MAP_TABLE_NAME_CELL_STYLE}">'
                            f"{html.escape(_cell_name_text(str(name)))}</p>",
                            unsafe_allow_html=True,
                        )
                    with r3:
                        if st.button(
                            "Go to",
                            key=f"geo_map_goto_{i}",
                            use_container_width=True,
                            disabled=not has_geom,
                        ):
                            st.session_state[SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW] = i
                            st.rerun()

    with st.container(key="geo_tbl_toggle_wrap"):
        if st.button(f"{total} {label_plural}", key=btn_key, use_container_width=True):
            st.session_state[SESSION_KEY_GEO_MAP_TABLE_EXPANDED] = not expanded
            st.rerun(scope="fragment")
