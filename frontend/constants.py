import os

API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    os.environ.get("LOCAL_API_BASE_URL", "http://localhost:8000"),
)
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "http://localhost:8501")

LAKE_COUNTY_ZOOM = 10.5

CHART_WIDTH = 600
CHART_HEIGHT = 400
CHART_NOMINAL_COLOR_SCHEME = "tableau10"
CHART_PIE_COLOR_SCHEME = "tableau20"


class COLOR:
    GRAY = (90, 90, 90)
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    NAVY = (26, 43, 76)
    LIGHT_BLUE = (88, 140, 200)
    HERO_SUBTITLE = (232, 238, 248)
    HEADER_BG = (240, 242, 248)
    ROW_ALT = (249, 250, 252)
    TABLE_ZEBRA = (237, 243, 248)
    DIVIDER = (210, 214, 220)
    ACCENT = (50, 100, 180)
    BLUE = (30, 80, 160)
    KPI_BG = (236, 241, 248)
    CARD_BLUE = (230, 240, 252)
    CARD_NAVY = (26, 43, 76)

CACHE_TTL_LAKE_COUNTY_BOUNDARY = 3600

LC_BOUNDARY_STYLE = {
    "color": "#004da8",
    "weight": 2,
    "fillColor": "#ffffff",
    "fillOpacity": 0,
}

SESSION_KEY_TOKEN = "token"
SESSION_KEY_MAP_CHAT_SESSION_ID = "map_chat_session_id"
SESSION_KEY_MAP_CHAT_MESSAGES = "map_chat_messages"
SESSION_KEY_MAP_AOI_DATA = "map_aoi_data"
SESSION_KEY_MAP_DATASET_DATA = "map_dataset_data"
SESSION_KEY_MAP_PROJECT_DATA = "map_project_data"
SESSION_KEY_MAP_PROJECT_MATCHES = "map_project_matches"
SESSION_KEY_MAP_PROJECT_LIST = "map_project_list"
SESSION_KEY_MAP_CHARTS_DATA = "map_charts_data"
SESSION_KEY_MAP_JURISDICTION_BOUNDARY = "map_jurisdiction_boundary"
SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY = "map_county_board_district_boundary"
SESSION_KEY_MAP_ACTIONS = "map_actions"
SESSION_KEY_GEO_RESULT_SUMMARY = "geo_result_summary"
SESSION_KEY_GEO_MAP_TABLE_EXPANDED = "geo_map_table_expanded"
SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW = "geo_map_table_focus_row"
SESSION_KEY_DATA_SOURCE = "data_source"
SESSION_KEY_MAP_CHAT_PENDING_INPUT = "map_chat_pending_input"
SESSION_KEY_MAP_CHAT_USER_INPUT = "map_chat_user_input"

GEO_CHAT_DEFER_TOOL_MESSAGE_TOOLS = frozenset(
    {"geo_query_geo_projects", "geo_build_result_summary"},
)

GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER = (
    "See the summary, listing, and charts in this panel for this reply."
)

GEO_NARRATIVE_SUGGESTIONS_DELIM = "---SUGGESTIONS---"

SESSION_KEY_GEO_STREAM_SCHEMA_SHOWN = "geo_stream_schema_shown"
SESSION_KEY_GEO_SCHEMA_EXPORT_SNAPSHOT = "geo_schema_export_snapshot"
GEO_CHAT_SCHEMA_CONTAINER_KEY = "geo_chat_schema_discovery"

GEO_CHAT_PLACEHOLDER_GEO_LAKE_COUNTY_LONG = (
    "Ask about soils in a jurisdiction or jurisdictions with a soil type"
)
GEO_CHAT_PLACEHOLDER_LAKE_COUNTY_LONG = "Search or filter Lake County projects"
GEO_CHAT_PLACEHOLDER_FOREST_LONG = "Ask about carbon removal for a location"
GEO_CHAT_PLACEHOLDER_SHORT = "Ask GeoAI"

DATA_SOURCES = {
    "Forest Carbon": "forest_carbon",
    "Lake County": "lake_county",
    "Geo Lake County": "geo_lake_county",
}

MAP_CHAT_INPUT_RADIUS = "28px"
MAP_CHAT_INPUT_COMPOSITE_MIN_HEIGHT = "104px"
MAP_CHAT_INPUT_TEXTAREA_MIN_HEIGHT = "36px"
MAP_CHAT_INPUT_TEXTAREA_MAX_LINE_COUNT = 5
MAP_CHAT_INPUT_TEXTAREA_VERTICAL_PAD_SUM_PX = 12
MAP_CHAT_INPUT_TEXTAREA_MAX_HEIGHT_FALLBACK = "132px"
MAP_CHAT_INPUT_TEXTAREA_PADDING = "6px 12px 6px 18px"
MAP_CHAT_INPUT_SHELL_INNER_PADDING = "10px 10px 0 10px"
MAP_CHAT_INPUT_FOOTER_MIN_HEIGHT = "36px"
MAP_CHAT_INPUT_FOOTER_PADDING = "6px 10px 6px 10px"
MAP_CHAT_INPUT_FONT_SIZE = "1rem"
MAP_CHAT_INPUT_LINE_HEIGHT = "1.5"
MAP_CHAT_GEMINI_LIGHT_SURFACE = "#ffffff"
MAP_CHAT_GEMINI_LIGHT_BORDER = "#dadce0"
MAP_CHAT_GEMINI_LIGHT_SHADOW = (
    "0 1px 2px rgba(60, 64, 67, 0.1), 0 4px 18px rgba(60, 64, 67, 0.08)"
)
MAP_CHAT_GEMINI_LIGHT_SEND_FILL = "#e8f0fe"
MAP_CHAT_GEMINI_LIGHT_SEND_ICON = "#202124"
MAP_CHAT_GEMINI_DARK_SURFACE = "#1e1f20"
MAP_CHAT_GEMINI_DARK_BORDER = "rgba(255, 255, 255, 0.14)"
MAP_CHAT_GEMINI_DARK_SHADOW = (
    "0 2px 14px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.05)"
)
MAP_CHAT_GEMINI_DARK_SEND_FILL = "rgba(255, 255, 255, 0.1)"
MAP_CHAT_GEMINI_DARK_SEND_ICON = "#e8eaed"
MAP_CHAT_GEMINI_LIGHT_COMPOSER_TEXT = MAP_CHAT_GEMINI_LIGHT_SEND_ICON
MAP_CHAT_GEMINI_DARK_COMPOSER_TEXT = MAP_CHAT_GEMINI_DARK_SEND_ICON


class MAP_CHAT_PDF:
    class DOCUMENT:
        TITLE = "Geo AI"

    class EXPORT:
        LABEL = "Export chat as PDF"
        FILENAME_PREFIX = "geo-ai-chat"

    class SECTION:
        SUMMARY = "Summary"
        FOLLOWUP = "Follow-up suggestions"
        SCHEMA = "Schema discovery"
        FIELDS = "Fields"
        RESULTS_DETAIL = "Results detail"
        RICH_CONTEXT = "Rich context"
        RECORD_DETAIL = "Record detail"
        PROJECT_LIST = "Project list"
        FULL_TABLE = "Full results table"
        CHARTS = "Charts"
        EXECUTIVE_SUMMARY = "Executive summary"
        DATA_SOURCE_SCHEMA = "Data source & schema"
        PROJECT_INVENTORY = "Project inventory"
        PORTFOLIO_SUMMARY = "Portfolio distribution summary"
        THEMATIC_CONTEXT = "Thematic context"
        SUGGESTED_FOLLOWUPS = "Suggested analytical follow-ups"

    class CHART:
        IMAGE_MAX_W_MM = 160.0
        IMAGE_BOTTOM_GAP_MM = 12.0
        SECTION_RESERVE_MM = 22.0

    class FULL_TABLE:
        MAX_COLUMNS = 12
        MAX_ROWS = 100

    class EXEC:
        class BANNER:
            LEAD = "GEO AI | DRAINAGE DISTRICT ANALYSIS"
            TAIL = "CONFIDENTIAL · STAKEHOLDER REVIEW"

        class COPY:
            HERO_KICKER = "GEO AI · DRAINAGE DISTRICT INTELLIGENCE"
            HERO_SUBKICKER = "REPORT"
            HERO_SUBTITLE = "Drainage District Project Review"

        PREPARED_BY = "Prepared by Geo AI"
        KEY_SCHEMA_LABEL = "Key schema fields"
        DISCLAIMER = (
            "This report was generated automatically by the Geo AI spatial intelligence system. "
            "All underlying data is sourced from Lake County GIS drainage district and project layers. "
            "Figures reflect records as of the session timestamp above."
        )

    class FOLLOWUP:
        CELL_PAD_MM = 1.4
        LINE_H_MM = 5.0
        NUM_COL_W_MM = 16.0

    class HERO:
        PAD_V_MM = 6.0

        class KICKER:
            PT = 10
            LINE_H_MM = 5.5

        class LN_AFTER:
            KICKERS_MM = 8.0
            TITLE_MM = 14.0
            SUBTITLE_MM = 12.0

        class TITLE:
            PT = 24
            CELL_H_MM = 12.0

        class SUBTITLE:
            PT = 13
            CELL_H_MM = 7.0

        class META:
            PT = 10
            LINE_H_MM = 5.0

    class KPI:
        VALUE_PT = 14
        VALUE_LINE_H_MM = 6.5
        VALUE_NUM_PT = 22
        VALUE_NUM_LINE_H_MM = 9.0
        LABEL_PT = 8
        LABEL_LINE_H_MM = 3.8
        TOP_PAD_MM = 3.0
        VALUE_LABEL_GAP_MM = 2.0
        BOTTOM_PAD_MM = 3.0

    class PROJECT_TABLE:
        INTRO_WRAP_HINT = (
            "Long text wraps within cells; row height follows the tallest cell in each row."
        )

    class INVENTORY:
        COL_WEIGHT_DEFAULT = 1.0
        COL_WEIGHT_WIDE = 2.6
        WIDE_COLUMN_KEYS = frozenset({"name", "description"})
        HEADER_LABELS: dict[str, str] = {
            "name": "NAME",
            "description": "DESCRIPTION",
            "projecttype": "PROJECT TYPE",
            "startyear": "START YEAR",
            "endyear": "END YEAR",
            "projectpartners": "PROJECT PARTNERS",
            "dollarsrequested": "DOLLARS REQUESTED",
            "estimatedcost": "ESTIMATED COST",
            "finalcost": "FINAL COST",
            "breakdown": "BREAKDOWN",
            "smcmanager": "SMC MANAGER",
            "agreementstatus": "AGREEMENT STATUS",
            "projectname": "PROJECT NAME",
            "objectid": "OBJECT ID",
            "globalid": "GLOBAL ID",
        }
        HDR_FONT_PT = 7
        HDR_LINE_H_MM = 4.0
        HDR_PAD_MM = 1.0

    class PORTFOLIO:
        CARD_HEIGHT_MM = 42.0
        CARD_INSET_MM = 2.5

        class LIGHT:
            TITLE_PT = 9
            TITLE_CELL_H_MM = 5.5
            BODY_PT = 9
            BODY_LINE_H_MM = 5.0
            GAP_AFTER_TITLE_MM = 3.0

        class NAVY:
            TITLE_PT = 9
            TITLE_LINE_H_MM = 3.8
            GAP_AFTER_TITLE_MM = 3.5
            VALUE_PT = 22
            VALUE_LINE_H_MM = 10.0
            GAP_AFTER_VALUE_MM = 3.0
            SUBTITLE_PT = 8
            SUBTITLE_LINE_H_MM = 4.5

    class SCHEMA_TABLE:
        COL_FIELD = "Field"
        COL_TYPE = "Type"
        COL_ALIAS = "Alias"


MAP_CHAT_PDF.EXEC.BANNER.FULL = (
    MAP_CHAT_PDF.EXEC.BANNER.LEAD + "  " + MAP_CHAT_PDF.EXEC.BANNER.TAIL
)

GEO_MAP_CHAT_MAP_COLUMNS_GAP = "medium"
GEO_MAP_STREAMLIT_KEY_CHAT_MAP_SPLIT = "geo_chat_map_split"
GEO_MAP_CHAT_MAP_COLUMN_WEIGHTS: list[int] = [1, 1]

GEO_MAP_IFRAME_MIN_HEIGHT_PX = 360
GEO_MAP_IFRAME_HEIGHT_VH_OFFSET_REM = 10.5
GEO_MAP_PANEL_TOP_SPACING_REM = 0.85
GEO_MAP_STREAMLIT_KEY_IFRAME_HOST = "geo_map_iframe_host"
GEO_MAP_STREAMLIT_KEY_BOTTOM_TABLE_WRAP = "geo_map_bottom_table_wrap"
GEO_MAP_STREAMLIT_KEY_TABLE_FLYOUT = "geo_map_table_flyout"
GEO_MAP_TABLE_FLYOUT_MAX_HEIGHT_CSS = "min(50vh, 400px)"
GEO_MAP_TABLE_FLYOUT_Z_INDEX = 40
STREAMLIT_DEBUG_GEO_MAP_ENV = "STREAMLIT_DEBUG_GEO_MAP"
GEO_MAP_ST_HEADER_REM = "3.75rem"
STREAMLIT_APP_TOP_BAR_TITLE = "Geo AI"
STREAMLIT_APP_TOP_BAR_TITLE_FONT_SIZE = "2.25rem"
STREAMLIT_APP_TOP_BAR_TITLE_PAD_LEFT = "1rem"
STREAMLIT_APP_TOP_BAR_TITLE_ELEMENT_ID = "zeno-app-top-bar-title"
GEO_MAP_RIGHT_PANEL_BORDER = "1px solid rgba(49,51,63,0.28)"

FOLIUM_STATIC_DEFAULT_WIDTH = 1200
FOLIUM_STATIC_DEFAULT_HEIGHT = 680
FOLIUM_ZOOMFIT_MAX_ZOOM = 18
FOLIUM_ZOOMFIT_PADDING_PX = 28
FOLIUM_ZOOMFIT_POINT_BUFFER_DEG = 0.0025

GEO_MAP_TABLE_NAME_DOM_MAX_CHARS = 512
GEO_MAP_TABLE_ROW_PADDING_Y_PX = 4
GEO_MAP_TABLE_ROW_PADDING_LEFT_PX = 8
GEO_MAP_TABLE_ROW_PADDING_RIGHT_PX = 3
GEO_MAP_TABLE_NAME_FONT_SIZE_REM = "0.78rem"
GEO_MAP_TABLE_ROW_ACTION_GAP_PX = 3
GEO_MAP_TABLE_HEADER_PADDING_Y_PX = 2
GEO_MAP_TABLE_HEADER_PADDING_X_PX = 7
GEO_MAP_TABLE_HEADER_GAP_PX = 6
GEO_MAP_TABLE_ROW_LINE_HEIGHT = 1.25
GEO_MAP_TABLE_FG_MUTED_LIGHT = "rgba(49,51,63,0.55)"
GEO_MAP_TABLE_FG_MUTED_DARK = "rgba(232,234,237,0.72)"
GEO_MAP_TABLE_FG_BODY_LIGHT = "rgba(49,51,63,0.92)"
GEO_MAP_TABLE_FG_BODY_DARK = "rgba(248,249,250,0.95)"
GEO_MAP_TABLE_TOGGLE_FG_LIGHT = "rgba(49,51,63,0.75)"
GEO_MAP_TABLE_TOGGLE_FG_DARK = "rgba(232,234,237,0.88)"
GEO_MAP_TABLE_TOGGLE_BG_LIGHT = "rgba(49,51,63,0.04)"
GEO_MAP_TABLE_TOGGLE_BG_DARK = "rgba(255,255,255,0.06)"
GEO_MAP_TABLE_TOGGLE_BORDER_LIGHT = "rgba(49,51,63,0.18)"
GEO_MAP_TABLE_TOGGLE_BORDER_DARK = "rgba(255,255,255,0.14)"
GEO_MAP_TABLE_TOGGLE_HOVER_BG_LIGHT = "rgba(49,51,63,0.09)"
GEO_MAP_TABLE_TOGGLE_HOVER_BG_DARK = "rgba(255,255,255,0.1)"
GEO_MAP_TABLE_DIVIDER_LIGHT = "rgba(49,51,63,0.08)"
GEO_MAP_TABLE_DIVIDER_DARK = "rgba(255,255,255,0.1)"
GEO_MAP_TABLE_HEAD_BG_LIGHT = "rgba(49,51,63,0.06)"
GEO_MAP_TABLE_HEAD_BG_DARK = "rgba(255,255,255,0.06)"
GEO_MAP_TABLE_HEAD_RULE_LIGHT = "rgba(49,51,63,0.12)"
GEO_MAP_TABLE_HEAD_RULE_DARK = "rgba(255,255,255,0.12)"
GEO_MAP_TABLE_GOTO_DISABLED_BG_LIGHT = "rgba(49,51,63,0.15)"
GEO_MAP_TABLE_GOTO_DISABLED_BG_DARK = "rgba(255,255,255,0.08)"
GEO_MAP_TABLE_GOTO_DISABLED_FG_LIGHT = "rgba(49,51,63,0.4)"
GEO_MAP_TABLE_GOTO_DISABLED_FG_DARK = "rgba(232,234,237,0.35)"
GEO_MAP_TABLE_NAME_CELL_STYLE = (
    "margin:0;padding:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
    f"max-width:100%;line-height:{GEO_MAP_TABLE_ROW_LINE_HEIGHT};"
    f"font-size:{GEO_MAP_TABLE_NAME_FONT_SIZE_REM}"
)
GEO_MAP_TABLE_GOTO_BUTTON_HEIGHT_PX = 26
GEO_MAP_TABLE_GOTO_BUTTON_PAD_X_PX = 6
GEO_MAP_TABLE_GOTO_BUTTON_FONT_SIZE_PX = 11
GEO_MAP_TABLE_GOTO_BUTTON_SHRINK_PCT = 30
GEO_MAP_TABLE_GOTO_BUTTON_MIN_WIDTH = "4.75rem"
GEO_MAP_TABLE_GOTO_BUTTON_BG = "#4C78A8"
GEO_MAP_TABLE_GOTO_BUTTON_HOVER = "#3a5d84"

_GEO_MAP_RIGHT_COL_A = 'section[data-testid="stMain"] [data-testid="column"]:last-of-type'
_GEO_MAP_RIGHT_COL_B = '[data-testid="stAppViewContainer"] [data-testid="column"]:last-of-type'
_GEO_MAP_COL_IFRAME_HOST_SEL = (
    f'{_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"], '
    f'{_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"]'
)
GEO_MAP_IFRAME_HOST_RIGHT_COL_SEL = _GEO_MAP_COL_IFRAME_HOST_SEL


def build_geo_map_column_css() -> str:
    mnh = GEO_MAP_IFRAME_MIN_HEIGHT_PX
    hdr = GEO_MAP_ST_HEADER_REM
    host_cap_global = f"calc((100vh - {hdr}) * 0.9)"
    folium_iframe_cap_global = f"min({FOLIUM_STATIC_DEFAULT_HEIGHT + 32}px, {host_cap_global})"
    sel = _GEO_MAP_COL_IFRAME_HOST_SEL
    return f"""
    {sel} [data-testid="stIFrame"],
    {sel} iframe {{
        min-height: {mnh}px;
        max-height: {folium_iframe_cap_global} !important;
        height: {folium_iframe_cap_global} !important;
        flex: 1 1 0;
        width: 100%;
        border: none;
    }}
    {sel} [data-testid="stIFrame"] {{
        flex: 1 1 0;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }}
    """


def build_geo_map_panel_result_rows_css(expanded: bool) -> str:
    hdr = GEO_MAP_ST_HEADER_REM
    host_flex = "6 1 0" if expanded else "9 1 0"
    host_cap = f"calc((100vh - {hdr}) * 0.55)" if expanded else f"calc((100vh - {hdr}) * 0.9)"
    folium_iframe_cap = f"min({FOLIUM_STATIC_DEFAULT_HEIGHT + 32}px, {host_cap})"
    sel_host = _GEO_MAP_COL_IFRAME_HOST_SEL
    sel_iframe = (
        f'{_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"] [data-testid="stIFrame"], '
        f'{_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"] iframe, '
        f'{_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"] [data-testid="stIFrame"], '
        f'{_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"] iframe'
    )
    wrap_sel = (
        f'{_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_table_debug_wrap"], '
        f'{_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_table_debug_wrap"]'
    )
    gmmc_inner_vb = (
        '[class*="geo_main_col_map"] > div > [data-testid="stVerticalBlock"], '
        '[class*="geo-main-col-map"] > div > [data-testid="stVerticalBlock"], '
        '[class*="geo_main_col_map"] > div > div > [data-testid="stVerticalBlock"], '
        '[class*="geo-main-col-map"] > div > div > [data-testid="stVerticalBlock"]'
    )
    gmmc_row_map = (
        '[class*="geo_main_col_map"] > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_iframe_host"]), '
        '[class*="geo-main-col-map"] > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_iframe_host"]), '
        '[class*="geo_main_col_map"] > div > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_iframe_host"]), '
        '[class*="geo-main-col-map"] > div > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_iframe_host"])'
    )
    gmmc_row_tbl = (
        '[class*="geo_main_col_map"] > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_table_debug_wrap"]), '
        '[class*="geo-main-col-map"] > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_table_debug_wrap"]), '
        '[class*="geo_main_col_map"] > div > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_table_debug_wrap"]), '
        '[class*="geo-main-col-map"] > div > div > [data-testid="stVerticalBlock"] > div:has([class*="geo_map_table_debug_wrap"])'
    )
    return f"""
    <style>
    [class*="geo_main_col_map"],
    [class*="geo-main-col-map"] {{
        overflow: visible !important;
    }}
    {gmmc_inner_vb} {{
        display: flex !important;
        flex-direction: column !important;
        min-height: 0 !important;
        overflow: visible !important;
    }}
    {gmmc_row_map} {{
        flex: {host_flex} !important;
        min-height: 0 !important;
        max-height: {host_cap} !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        flex-shrink: 1 !important;
        position: relative !important;
        z-index: 1 !important;
    }}
    {gmmc_row_map} [data-testid="stIFrame"] {{
        align-self: stretch !important;
        width: 100% !important;
        max-width: 100% !important;
        max-height: {folium_iframe_cap} !important;
        height: auto !important;
    }}
    {gmmc_row_tbl} {{
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        flex-grow: 0 !important;
        min-height: 0 !important;
        overflow: visible !important;
        position: relative !important;
        z-index: 12 !important;
    }}
    {sel_host} {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: 100% !important;
        margin-top: 0 !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    {sel_host} > div {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    {sel_host} [data-testid="stVerticalBlock"] {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    {sel_iframe} {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: {folium_iframe_cap} !important;
        height: {folium_iframe_cap} !important;
        width: 100% !important;
    }}
    {_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"] [data-testid="stIFrame"],
    {_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"] [data-testid="stIFrame"] {{
        max-height: {folium_iframe_cap} !important;
        min-height: 0 !important;
        height: {folium_iframe_cap} !important;
        overflow: hidden !important;
    }}
    {_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"] [data-testid="stIFrame"] iframe,
    {_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"] iframe,
    {_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"] [data-testid="stIFrame"] iframe,
    {_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"] iframe {{
        max-height: {folium_iframe_cap} !important;
        min-height: 0 !important;
        height: {folium_iframe_cap} !important;
        width: 100% !important;
    }}
    {_GEO_MAP_RIGHT_COL_A} [class*="st-key-geo_map_iframe_host"],
    {_GEO_MAP_RIGHT_COL_B} [class*="st-key-geo_map_iframe_host"] {{
        border: {GEO_MAP_RIGHT_PANEL_BORDER} !important;
        border-radius: 8px !important;
        box-sizing: border-box !important;
    }}
    {wrap_sel} {{
        flex-shrink: 0 !important;
        margin-top: 0 !important;
        padding: 0 !important;
        overflow: visible !important;
    }}
    {wrap_sel} > div,
    {wrap_sel} > div > [data-testid="stVerticalBlock"] {{
        overflow: visible !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
        gap: 0 !important;
    }}
    </style>
    """


def build_map_chat_input_css() -> str:
    r = MAP_CHAT_INPUT_RADIUS
    outer_min = MAP_CHAT_INPUT_COMPOSITE_MIN_HEIGHT
    ta_min = MAP_CHAT_INPUT_TEXTAREA_MIN_HEIGHT
    ta_lines = MAP_CHAT_INPUT_TEXTAREA_MAX_LINE_COUNT
    ta_pad_v = MAP_CHAT_INPUT_TEXTAREA_VERTICAL_PAD_SUM_PX
    ta_max_fb = MAP_CHAT_INPUT_TEXTAREA_MAX_HEIGHT_FALLBACK
    lh_num = float(MAP_CHAT_INPUT_LINE_HEIGHT)
    ta_max = f"calc({lh_num * ta_lines}em + {ta_pad_v}px)"
    ta_pad = MAP_CHAT_INPUT_TEXTAREA_PADDING
    fs = MAP_CHAT_INPUT_FONT_SIZE
    lh = MAP_CHAT_INPUT_LINE_HEIGHT
    gls = MAP_CHAT_GEMINI_LIGHT_SURFACE
    glb = MAP_CHAT_GEMINI_LIGHT_BORDER
    gld = MAP_CHAT_GEMINI_LIGHT_SHADOW
    gds = MAP_CHAT_GEMINI_DARK_SURFACE
    gdb = MAP_CHAT_GEMINI_DARK_BORDER
    gdd = MAP_CHAT_GEMINI_DARK_SHADOW
    glsf = MAP_CHAT_GEMINI_LIGHT_SEND_FILL
    glsi = MAP_CHAT_GEMINI_LIGHT_SEND_ICON
    gdsf = MAP_CHAT_GEMINI_DARK_SEND_FILL
    gdsi = MAP_CHAT_GEMINI_DARK_SEND_ICON
    glct = MAP_CHAT_GEMINI_LIGHT_COMPOSER_TEXT
    gdct = MAP_CHAT_GEMINI_DARK_COMPOSER_TEXT
    shell_pad = MAP_CHAT_INPUT_SHELL_INNER_PADDING
    foot_min = MAP_CHAT_INPUT_FOOTER_MIN_HEIGHT
    foot_pad = MAP_CHAT_INPUT_FOOTER_PADDING
    shell = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] > div, '
        '[data-testid="stAppViewContainer"] div.stChatInput[data-testid="stChatInput"] > div, '
        '.stChatFloatingInputContainer [data-testid="stChatInput"] > div, '
        '[data-testid="stChatInput"] > div'
    )
    shell_fw = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"]:focus-within > div, '
        '.stChatFloatingInputContainer [data-testid="stChatInput"]:focus-within > div, '
        '[data-testid="stChatInput"]:focus-within > div'
    )
    ta_sel = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea, '
        '[data-testid="stChatInputTextArea"]'
    )
    root_sel = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] [data-baseweb="textarea"], '
        '[data-testid="stChatInput"] [data-baseweb="textarea"]'
    )
    flex_ta = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] > div > div:has(textarea), '
        '.stChatFloatingInputContainer [data-testid="stChatInput"] > div > div:has(textarea), '
        '[data-testid="stChatInput"] > div > div:has(textarea)'
    )
    btn_row = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] > div > div:has(button), '
        '.stChatFloatingInputContainer [data-testid="stChatInput"] > div > div:has(button), '
        '[data-testid="stChatInput"] > div > div:has(button)'
    )
    instr_row = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] '
        '> div > div:has([data-testid="InputInstructions"]), '
        '.stChatFloatingInputContainer [data-testid="stChatInput"] '
        '> div > div:has([data-testid="InputInstructions"]), '
        '[data-testid="stChatInput"] > div > div:has([data-testid="InputInstructions"])'
    )
    upload_row = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] '
        '> div > div:has([data-testid="stChatInputFileUploadButton"]), '
        '.stChatFloatingInputContainer [data-testid="stChatInput"] '
        '> div > div:has([data-testid="stChatInputFileUploadButton"]), '
        '[data-testid="stChatInput"] > div > div:has([data-testid="stChatInputFileUploadButton"])'
    )
    btn_sel = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] button, '
        '[data-testid="stChatInputSubmitButton"]'
    )
    btn_hover_sel = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] button:hover, '
        '[data-testid="stChatInputSubmitButton"]:hover'
    )
    btn_focus_sel = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] button:focus-visible, '
        '[data-testid="stChatInputSubmitButton"]:focus-visible'
    )
    wrap_clear = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] [data-baseweb="textarea"], '
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] '
        '[data-baseweb="textarea"] > div, '
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"] [data-baseweb="input"], '
        '[data-testid="stChatInput"] [data-baseweb="textarea"], '
        '[data-testid="stChatInput"] [data-baseweb="textarea"] > div, '
        '[data-testid="stChatInput"] [data-baseweb="input"]'
    )
    outer_chat = (
        '[data-testid="stAppViewContainer"] [data-testid="stChatInput"], '
        '[data-testid="stChatInput"]'
    )
    return f"""
    [data-testid="stChatInputContainer"], .stChatFloatingInputContainer {{
        margin-bottom: 5.5rem !important;
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        padding: 0 !important;
    }}
    {outer_chat} {{
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        height: auto !important;
    }}
    {shell} {{
        background-color: {gls} !important;
        border: 1px solid {glb} !important;
        border-radius: {r} !important;
        box-shadow: {gld} !important;
        min-height: {outer_min} !important;
        height: auto !important;
        max-height: none !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        align-content: stretch !important;
        padding: {shell_pad} !important;
        gap: 0 !important;
        overflow: hidden !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
    }}
    @media (prefers-color-scheme: dark) {{
        {shell} {{
            background-color: {gds} !important;
            border: 1px solid {gdb} !important;
            box-shadow: {gdd} !important;
        }}
    }}
    @supports (background-color: light-dark(white, black)) {{
        {shell} {{
            background-color: light-dark({gls}, {gds}) !important;
            border-color: light-dark({glb}, {gdb}) !important;
        }}
    }}
    {shell_fw} {{
        border-color: var(--st-primary-color, #1a73e8) !important;
        box-shadow:
            0 0 0 1px var(--st-primary-color, #1a73e8),
            0 2px 16px rgba(26, 115, 232, 0.22) !important;
    }}
    @media (prefers-color-scheme: dark) {{
        {shell_fw} {{
            border-color: var(--st-primary-color, #8ab4f8) !important;
            box-shadow:
                0 0 0 1px var(--st-primary-color, #8ab4f8),
                0 2px 18px rgba(138, 180, 248, 0.28) !important;
        }}
    }}
    {flex_ta} {{
        flex: 0 1 auto !important;
        width: 100% !important;
        min-width: 0 !important;
        min-height: auto !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
        display: flex !important;
        flex-direction: column !important;
        align-self: stretch !important;
    }}
    {instr_row} {{
        flex: 0 0 auto !important;
        width: 100% !important;
        min-width: 0 !important;
    }}
    {upload_row} {{
        flex: 0 0 auto !important;
        width: 100% !important;
        min-width: 0 !important;
    }}
    {root_sel} {{
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        flex: 0 1 auto !important;
        min-height: auto !important;
        height: auto !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
    }}
    {ta_sel} {{
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        background-color: transparent !important;
        color: {glct} !important;
        caret-color: {glct} !important;
        font-size: {fs} !important;
        line-height: {lh} !important;
        padding: {ta_pad} !important;
        min-height: {ta_min} !important;
        max-height: {ta_max_fb} !important;
        max-height: {ta_max} !important;
        width: 100% !important;
        box-sizing: border-box !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
        resize: none !important;
        border-radius: 0 !important;
    }}
    @media (prefers-color-scheme: dark) {{
        {ta_sel},
        {wrap_clear} {{
            color: {gdct} !important;
        }}
        {ta_sel} {{
            caret-color: {gdct} !important;
        }}
    }}
    @supports (color: light-dark(white, black)) {{
        {ta_sel},
        {wrap_clear} {{
            color: light-dark({glct}, {gdct}) !important;
        }}
        {ta_sel} {{
            caret-color: light-dark({glct}, {gdct}) !important;
        }}
    }}
    [data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stChatInputTextArea"]::placeholder {{
        color: var(--st-text-color, #5f6368) !important;
        opacity: 0.85 !important;
    }}
    @media (prefers-color-scheme: dark) {{
        [data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea::placeholder,
        [data-testid="stChatInputTextArea"]::placeholder {{
            color: var(--st-text-color, #9aa0a6) !important;
            opacity: 0.9 !important;
        }}
    }}
    [data-testid="stAppViewContainer"] [data-testid="stChatInput"]:focus-within textarea::placeholder,
    [data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea:focus::placeholder,
    [data-testid="stChatInputTextArea"]:focus::placeholder {{
        opacity: 0 !important;
        color: transparent !important;
    }}
    [data-testid="stAppViewContainer"] [data-testid="stChatInput"]:focus-within textarea::-webkit-input-placeholder,
    [data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea:focus::-webkit-input-placeholder,
    [data-testid="stChatInputTextArea"]:focus::-webkit-input-placeholder {{
        opacity: 0 !important;
        color: transparent !important;
    }}
    {wrap_clear} {{
        background: transparent !important;
        background-color: transparent !important;
        border-radius: 0 !important;
    }}
    {btn_row} {{
        position: relative !important;
        top: auto !important;
        right: auto !important;
        bottom: auto !important;
        left: auto !important;
        inset: auto !important;
        width: 100% !important;
        max-width: 100% !important;
        height: auto !important;
        min-height: {foot_min} !important;
        margin: 0 !important;
        margin-top: 0 !important;
        padding: {foot_pad} !important;
        display: flex !important;
        flex-direction: row !important;
        justify-content: flex-end !important;
        align-items: center !important;
        align-self: stretch !important;
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        pointer-events: auto !important;
        border-top: none !important;
        box-sizing: border-box !important;
    }}
    {btn_sel} {{
        color: {glsi} !important;
        align-self: center !important;
        width: 2.5rem !important;
        height: 2.5rem !important;
        min-width: 2.5rem !important;
        min-height: 2.5rem !important;
        border-radius: 50% !important;
        margin: 0 !important;
        flex-shrink: 0 !important;
        background-color: {glsf} !important;
    }}
    @media (prefers-color-scheme: dark) {{
        {btn_sel} {{
            color: {gdsi} !important;
            background-color: {gdsf} !important;
        }}
    }}
    @supports (color: light-dark(white, black)) {{
        {btn_sel} {{
            color: light-dark({glsi}, {gdsi}) !important;
            background-color: light-dark({glsf}, {gdsf}) !important;
        }}
    }}
    {btn_hover_sel} {{
        color: var(--st-primary-color, #1967d2) !important;
        background-color: rgba(26, 115, 232, 0.18) !important;
    }}
    @media (prefers-color-scheme: dark) {{
        {btn_hover_sel} {{
            color: var(--st-primary-color, #8ab4f8) !important;
            background-color: rgba(138, 180, 248, 0.22) !important;
        }}
    }}
    {btn_focus_sel} {{
        outline: 2px solid var(--st-primary-color, #1a73e8) !important;
        outline-offset: 2px !important;
    }}
    @media (prefers-color-scheme: dark) {{
        {btn_focus_sel} {{
            outline-color: var(--st-primary-color, #8ab4f8) !important;
        }}
    }}
    """


FOREST_CARBON_REMOVALS_DATASET = {
    "dataset_id": 10,
    "source": "GFW",
    "dataset_name": "Forest Carbon Gross Removals",
    "data_layer": "Forest Carbon Gross Removals",
    "tile_url": "https://tiles.globalforestwatch.org/gfw_forest_carbon_gross_removals/latest/dynamic/{z}/{x}/{y}.png?tree_cover_density_threshold=30",
    "context_layer": None,
    "threshold": "30",
}
