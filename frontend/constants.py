import os

API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    os.environ.get("LOCAL_API_BASE_URL", "http://localhost:8000"),
)
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "http://localhost:8501")

LAKE_COUNTY_ZOOM = 10.5

CHART_WIDTH = 600
CHART_HEIGHT = 400

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
SESSION_KEY_DATA_SOURCE = "data_source"
SESSION_KEY_MAP_CHAT_PENDING_INPUT = "map_chat_pending_input"
SESSION_KEY_MAP_CHAT_USER_INPUT = "map_chat_user_input"

DATA_SOURCES = {
    "Forest Carbon": "forest_carbon",
    "Lake County": "lake_county",
    "Geo Lake County": "geo_lake_county",
}

FOREST_CARBON_REMOVALS_DATASET = {
    "dataset_id": 10,
    "source": "GFW",
    "dataset_name": "Forest Carbon Gross Removals",
    "data_layer": "Forest Carbon Gross Removals",
    "tile_url": "https://tiles.globalforestwatch.org/gfw_forest_carbon_gross_removals/latest/dynamic/{z}/{x}/{y}.png?tree_cover_density_threshold=30",
    "context_layer": None,
    "threshold": "30",
}
