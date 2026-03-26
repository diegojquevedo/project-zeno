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
GEO_CHAT_SCHEMA_CONTAINER_KEY = "geo_chat_schema_discovery"

DATA_SOURCES = {
    "Forest Carbon": "forest_carbon",
    "Lake County": "lake_county",
    "Geo Lake County": "geo_lake_county",
}

MAP_CHAT_INPUT_SURFACE = "#ffffff"
MAP_CHAT_INPUT_BORDER = "#dadce0"
MAP_CHAT_INPUT_BORDER_FOCUS = "#1e88e5"
MAP_CHAT_INPUT_SHADOW = (
    "0 1px 2px rgba(60, 64, 67, 0.14), 0 1px 3px 1px rgba(60, 64, 67, 0.08)"
)
MAP_CHAT_INPUT_SHADOW_FOCUS = (
    "0 1px 3px rgba(30, 136, 229, 0.22), 0 2px 6px 2px rgba(60, 64, 67, 0.06)"
)
MAP_CHAT_INPUT_TEXT = "#1f1f1f"
MAP_CHAT_INPUT_PLACEHOLDER = "#5f6368"
MAP_CHAT_INPUT_SEND_ICON = "#5f6368"
MAP_CHAT_INPUT_SEND_ICON_HOVER = "#1e88e5"
MAP_CHAT_INPUT_RADIUS = "9999px"
MAP_CHAT_INPUT_MIN_HEIGHT = "44px"
MAP_CHAT_INPUT_TEXTAREA_MIN_HEIGHT = "38px"
MAP_CHAT_INPUT_TEXTAREA_PADDING = "10px 14px 10px 26px"
MAP_CHAT_INPUT_FONT_SIZE = "1rem"
MAP_CHAT_INPUT_LINE_HEIGHT = "1.45"

GEO_MAP_IFRAME_MIN_HEIGHT_PX = 480
GEO_MAP_IFRAME_HEIGHT_VH_OFFSET_REM = 10.5
GEO_MAP_PANEL_TOP_SPACING_REM = 0.85

FOLIUM_STATIC_DEFAULT_WIDTH = 1200
FOLIUM_STATIC_DEFAULT_HEIGHT = 820


def build_geo_map_column_css() -> str:
    mnh = GEO_MAP_IFRAME_MIN_HEIGHT_PX
    top_gap = GEO_MAP_PANEL_TOP_SPACING_REM
    rem = GEO_MAP_IFRAME_HEIGHT_VH_OFFSET_REM + top_gap
    return f"""
    div[data-testid="stHorizontalBlock"] {{
        align-items: stretch !important;
    }}
    [data-testid="column"]:last-of-type {{
        display: flex !important;
        flex-direction: column !important;
        align-self: stretch !important;
    }}
    [data-testid="column"]:last-of-type > div {{
        flex: 1 1 auto !important;
        min-height: 0 !important;
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    [data-testid="column"]:last-of-type > div > *:first-child {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}
    [class*="st-key-geo_map_panel"] {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        padding-top: {top_gap}rem !important;
        box-sizing: border-box !important;
    }}
    [class*="st-key-geo_map_panel"] > div:first-child {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }}
    [class*="st-key-geo_map_panel"] [data-testid="stVerticalBlock"] {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 0 !important;
        overflow: hidden !important;
    }}
    [class*="st-key-geo_map_panel"] [data-testid="stVerticalBlock"] > [data-testid="element-container"]:first-of-type,
    [class*="st-key-geo_map_panel"] [data-testid="stVerticalBlock"] > div:first-of-type {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }}
    [class*="st-key-geo_map_panel"] [data-testid="stVerticalBlock"] > [data-testid="element-container"]:not(:first-of-type),
    [class*="st-key-geo_map_panel"] [data-testid="stVerticalBlock"] > div:not(:first-of-type) {{
        flex: 0 0 auto !important;
    }}
    [class*="st-key-geo_map_panel"] [data-testid="stIFrame"],
    [class*="st-key-geo_map_panel"] iframe {{
        flex: 1 1 0 !important;
        min-height: {mnh}px !important;
        height: 100% !important;
        max-height: calc(100vh - {rem}rem) !important;
        width: 100% !important;
        border: none !important;
    }}
    """


def build_map_chat_input_css() -> str:
    t = {
        "surface": MAP_CHAT_INPUT_SURFACE,
        "border": MAP_CHAT_INPUT_BORDER,
        "border_focus": MAP_CHAT_INPUT_BORDER_FOCUS,
        "shadow": MAP_CHAT_INPUT_SHADOW,
        "shadow_focus": MAP_CHAT_INPUT_SHADOW_FOCUS,
        "text": MAP_CHAT_INPUT_TEXT,
        "placeholder": MAP_CHAT_INPUT_PLACEHOLDER,
        "send": MAP_CHAT_INPUT_SEND_ICON,
        "send_hover": MAP_CHAT_INPUT_SEND_ICON_HOVER,
        "radius": MAP_CHAT_INPUT_RADIUS,
        "min_h": MAP_CHAT_INPUT_MIN_HEIGHT,
        "ta_min_h": MAP_CHAT_INPUT_TEXTAREA_MIN_HEIGHT,
        "ta_pad": MAP_CHAT_INPUT_TEXTAREA_PADDING,
        "fs": MAP_CHAT_INPUT_FONT_SIZE,
        "lh": MAP_CHAT_INPUT_LINE_HEIGHT,
    }
    return """
    [data-testid="stChatInputContainer"], .stChatFloatingInputContainer {{
        margin-bottom: 5.5rem !important;
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        padding: 0 !important;
    }}
    [data-testid="stChatInput"] {{
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }}
    [data-testid="stChatInput"] > div {{
        background: {surface} !important;
        border: 1px solid {border} !important;
        border-radius: {radius} !important;
        box-shadow: {shadow} !important;
        min-height: {min_h} !important;
        align-items: center !important;
        padding: 1px 5px 1px 1px !important;
        overflow: hidden !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
    }}
    [data-testid="stChatInput"]:focus-within > div {{
        border-color: {border_focus} !important;
        box-shadow: {shadow_focus} !important;
    }}
    [data-testid="stChatInput"] [data-baseweb="base-input"],
    [data-testid="stChatInput"] textarea {{
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: {surface} !important;
        background-color: {surface} !important;
        color: {text} !important;
        font-size: {fs} !important;
        line-height: {lh} !important;
        padding: {ta_pad} !important;
        min-height: {ta_min_h} !important;
        max-height: 8rem !important;
        resize: none !important;
        border-radius: 0 !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: {placeholder} !important;
        opacity: 1 !important;
    }}
    [data-testid="stChatInput"] [data-baseweb="textarea"],
    [data-testid="stChatInput"] [data-baseweb="textarea"] > div,
    [data-testid="stChatInput"] [data-baseweb="input"] {{
        background: {surface} !important;
        background-color: {surface} !important;
        border-radius: 0 !important;
    }}
    [data-testid="stChatInput"] button {{
        color: {send} !important;
        align-self: center !important;
    }}
    [data-testid="stChatInput"] button:hover {{
        color: {send_hover} !important;
        background-color: transparent !important;
    }}
    [data-testid="stChatInput"] button:focus-visible {{
        outline: 2px solid {border_focus} !important;
        outline-offset: 2px !important;
    }}
    """.format(**t)


FOREST_CARBON_REMOVALS_DATASET = {
    "dataset_id": 10,
    "source": "GFW",
    "dataset_name": "Forest Carbon Gross Removals",
    "data_layer": "Forest Carbon Gross Removals",
    "tile_url": "https://tiles.globalforestwatch.org/gfw_forest_carbon_gross_removals/latest/dynamic/{z}/{x}/{y}.png?tree_cover_density_threshold=30",
    "context_layer": None,
    "threshold": "30",
}
