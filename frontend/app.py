"""
Map Chat - Main entry point. Runs directly without redirect.
"""
import json
import os
import uuid

import streamlit as st
from client import ZenoClient
from dotenv import load_dotenv
from utils import API_BASE_URL, render_dataset_map, render_stream

load_dotenv()

FOREST_CARBON_REMOVALS_DATASET = {
    "dataset_id": 10,
    "source": "GFW",
    "dataset_name": "Forest Carbon Gross Removals",
    "data_layer": "Forest Carbon Gross Removals",
    "tile_url": "https://tiles.globalforestwatch.org/gfw_forest_carbon_gross_removals/latest/dynamic/{z}/{x}/{y}.png?tree_cover_density_threshold=30",
    "context_layer": None,
    "threshold": "30",
}

# Lake County Project layers (approved and submitted use same geometry layers)
LAKE_COUNTY_LAYERS = [
    {
        "layer_id": "project_points",
        "dataset_name": "Project Points",
        "data_layer": "Project Points",
        "arcgis_url": "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/SMCAllProjectLayers/FeatureServer/27",
        "layer_type": "FeatureServer",
        "geometry_type": "point",
        "source": "Lake County",
        "description": "Point locations of stormwater projects (approved and submitted) in Lake County.",
    },
    {
        "layer_id": "project_areas",
        "dataset_name": "Project Areas",
        "data_layer": "Project Areas",
        "arcgis_url": "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/SMCAllProjectLayers/FeatureServer/29",
        "layer_type": "FeatureServer",
        "geometry_type": "polygon",
        "source": "Lake County",
        "description": "Area geometries of stormwater projects (approved and submitted) in Lake County.",
    },
    {
        "layer_id": "project_lines",
        "dataset_name": "Project Lines",
        "data_layer": "Project Lines",
        "arcgis_url": "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/SMCAllProjectLayers/FeatureServer/23",
        "layer_type": "FeatureServer",
        "geometry_type": "polyline",
        "source": "Lake County",
        "description": "Linear geometries of stormwater projects (approved and submitted) in Lake County.",
    },
    {
        "layer_id": "project_representative_points",
        "dataset_name": "Project Representative Points",
        "data_layer": "Project Representative Points",
        "arcgis_url": "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/SMCAllProjectLayers/FeatureServer/30",
        "layer_type": "FeatureServer",
        "geometry_type": "point",
        "source": "Lake County",
        "description": "Representative point locations of stormwater projects in Lake County.",
    },
]
LAKE_COUNTY_DEFAULT_LAYER = LAKE_COUNTY_LAYERS[1]  # areas

# Lake County bounds as GeoJSON polygon (WGS84)
LAKE_COUNTY_AOI = {
    "source": "lake_county",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [-88.33, 41.99],
            [-87.67, 41.99],
            [-87.67, 42.69],
            [-88.33, 42.69],
            [-88.33, 41.99],
        ]],
    },
}

DATA_SOURCES = {"Forest Carbon": "forest_carbon", "Lake County": "lake_county"}

if "map_chat_session_id" not in st.session_state:
    st.session_state.map_chat_session_id = str(uuid.uuid4())
if "map_chat_messages" not in st.session_state:
    st.session_state.map_chat_messages = []
if "map_aoi_data" not in st.session_state:
    st.session_state.map_aoi_data = None
if "map_dataset_data" not in st.session_state:
    st.session_state.map_dataset_data = FOREST_CARBON_REMOVALS_DATASET
if "map_project_data" not in st.session_state:
    st.session_state.map_project_data = None
if "map_project_matches" not in st.session_state:
    st.session_state.map_project_matches = None
if "map_project_list" not in st.session_state:
    st.session_state.map_project_list = None
if "data_source" not in st.session_state:
    st.session_state.data_source = "forest_carbon"

token = st.query_params.get("token")
if token:
    st.session_state["token"] = token
    st.query_params.clear()

if "token" not in st.session_state or st.session_state["token"] is None:
    auto_token = os.environ.get("AUTO_LOGIN_TOKEN")
    if auto_token and auto_token != "<your-gfw-jwt-token>":
        st.session_state["token"] = auto_token
    else:
        st.session_state["token"] = None

st.set_page_config(
    page_title="Map Chat - Zeno",
    page_icon="🌎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    button[aria-label="Expand sidebar"],
    button[aria-label="Collapse sidebar"],
    [data-testid="stSidebarCollapsedButton"] { display: none !important; }
    [data-testid="column"]:first-child {
        max-height: 85vh;
        overflow-y: auto;
        padding-right: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

chat_col, map_col = st.columns([1, 1])

with chat_col:
    st.header("Geo AI")
    st.write("This is a friendly prompt-based system to filter and analyze mapping data.")

    data_source = st.selectbox(
        "Data source",
        options=list(DATA_SOURCES.keys()),
        index=0 if st.session_state.data_source == "forest_carbon" else 1,
        key="data_source_select",
    )
    ds_value = DATA_SOURCES[data_source]
    if ds_value != st.session_state.data_source:
        st.session_state.data_source = ds_value
        if ds_value == "lake_county":
            st.session_state.map_dataset_data = LAKE_COUNTY_DEFAULT_LAYER
            st.session_state.map_aoi_data = LAKE_COUNTY_AOI
        else:
            st.session_state.map_dataset_data = FOREST_CARBON_REMOVALS_DATASET
            st.session_state.map_aoi_data = None
            st.session_state.map_project_data = None
            st.session_state.map_project_matches = None
            st.session_state.map_project_list = None

    if st.session_state.data_source == "lake_county":
        st.caption("Ask about a project by name to see its geometry and details.")

    st.divider()

    for message in st.session_state.map_chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    client = ZenoClient(base_url=API_BASE_URL, token=st.session_state.token)
    quota_info = client.get_quota_info()
    remaining_prompts = quota_info["promptQuota"] - quota_info["promptsUsed"]

    if "map_chat_pending_input" not in st.session_state:
        st.session_state.map_chat_pending_input = None

    def handle_map_chat_input():
        current = st.session_state.get("map_chat_user_input", "")
        if current and current.strip():
            st.session_state.map_chat_pending_input = current.strip()

    placeholder = (
        "Ask about projects in Lake County"
        if st.session_state.data_source == "lake_county"
        else "Ask about carbon removal for a location"
    )
    user_input = st.chat_input(
        f"{placeholder} (remaining: {remaining_prompts})",
        key="map_chat_user_input",
        on_submit=handle_map_chat_input,
    )

    if st.session_state.map_chat_pending_input:
        user_input = st.session_state.map_chat_pending_input
        st.session_state.map_chat_pending_input = None

    if user_input:
        st.session_state.map_chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        dataset = (
            st.session_state.map_dataset_data
            if st.session_state.data_source == "lake_county"
            else FOREST_CARBON_REMOVALS_DATASET
        )
        ui_context = {
            "data_source_selected": {"data_source": st.session_state.data_source},
            "dataset_selected": {"dataset": dataset},
            "aoi_selected": (
                {
                    "aoi": LAKE_COUNTY_AOI,
                    "aoi_name": "Lake County",
                    "subregion_aois": [],
                    "subregion": "",
                    "subtype": "",
                }
                if st.session_state.data_source == "lake_county"
                else None
            ),
        }
        ui_context = {k: v for k, v in ui_context.items() if v is not None}

        with st.chat_message("assistant"):
            for stream in client.chat(
                query=user_input,
                user_persona="Researcher",
                ui_context=ui_context,
                thread_id=st.session_state.map_chat_session_id,
                user_id=st.session_state.get("user", {}).get("email", "anonymous"),
            ):
                try:
                    if stream.get("node") == "trace_info":
                        update = json.loads(stream["update"])
                        if "trace_id" in update:
                            st.success(f"Trace ID: {update['trace_id']}")
                        continue
                    update = json.loads(stream["update"])
                    if "aoi" in update:
                        st.session_state.map_aoi_data = update["aoi"]
                    if "dataset" in update:
                        st.session_state.map_dataset_data = update["dataset"]
                    if "project_result" in update:
                        pr = update["project_result"]
                        if pr is None:
                            st.session_state.map_project_data = None
                            st.session_state.map_project_matches = None
                            st.session_state.map_project_list = None
                        elif pr.get("list"):
                            st.session_state.map_project_list = pr.get("matches", [])
                            st.session_state.map_project_data = None
                            st.session_state.map_project_matches = None
                        elif pr.get("multiple"):
                            st.session_state.map_project_matches = pr.get("matches", [])
                            st.session_state.map_project_data = None
                            st.session_state.map_project_list = None
                        else:
                            st.session_state.map_project_data = pr
                            st.session_state.map_project_matches = None
                            st.session_state.map_project_list = None
                    render_stream(stream, skip_maps=True)
                except Exception as e:
                    st.error(f"Error processing stream: {e}")

with map_col:
    if st.session_state.data_source == "lake_county":
        matches = st.session_state.map_project_matches
        project_list = st.session_state.map_project_list
        if matches and not st.session_state.map_project_data and not project_list:
            st.write("**Select a project to view on the map:**")
            cols = st.columns(min(len(matches), 3))
            for i, m in enumerate(matches):
                name = m.get("attributes", {}).get("Name", f"Project {i + 1}")
                with cols[i % 3]:
                    if st.button(
                        name[:60] + ("..." if len(name) > 60 else ""),
                        key=f"lc_project_{i}",
                    ):
                        st.session_state.map_project_data = {
                            "rep_point_geojson": m.get("rep_point_geojson"),
                            "geometry_geojson": m.get("geometry_geojson"),
                            "geojson": m.get("geometry_geojson") or m.get("rep_point_geojson"),
                            "attributes": m.get("attributes", {}),
                        }
                        st.session_state.map_project_matches = None
                        st.rerun()
    render_dataset_map(
        st.session_state.map_dataset_data,
        st.session_state.map_aoi_data,
        show_title=True,
        width=1200,
        height=550,
        project_data=st.session_state.map_project_data
        if st.session_state.data_source == "lake_county"
        else None,
        project_list=st.session_state.map_project_list
        if st.session_state.data_source == "lake_county"
        else None,
    )
