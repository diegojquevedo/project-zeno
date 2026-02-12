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

if "map_chat_session_id" not in st.session_state:
    st.session_state.map_chat_session_id = str(uuid.uuid4())
if "map_chat_messages" not in st.session_state:
    st.session_state.map_chat_messages = []
if "map_aoi_data" not in st.session_state:
    st.session_state.map_aoi_data = None
if "map_dataset_data" not in st.session_state:
    st.session_state.map_dataset_data = FOREST_CARBON_REMOVALS_DATASET

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
    st.header("Vizonomy AI")
    st.write("This is a friendly prompt-based system to filter and analyze mapping data.")
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

    user_input = st.chat_input(
        f"Ask about carbon removal for a location (remaining: {remaining_prompts})",
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

        ui_context = {"dataset_selected": {"dataset": FOREST_CARBON_REMOVALS_DATASET}}

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
                    render_stream(stream, skip_maps=True)
                except Exception as e:
                    st.error(f"Error processing stream: {e}")

with map_col:
    render_dataset_map(
        st.session_state.map_dataset_data,
        st.session_state.map_aoi_data,
        show_title=True,
        width=1200,
        height=550,
    )
