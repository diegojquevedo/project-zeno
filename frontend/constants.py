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
        color: var(--st-text-color, #262730) !important;
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
