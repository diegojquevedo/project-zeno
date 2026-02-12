"""
Map Conversational: Chat with the agent and see responses on an interactive map.

- Left (30%): Chat input and conversation.
- Right (70%): Map showing Forest Carbon Gross Removals layer.
- AOI (zoom, outline) comes from the agent based on the user's question (e.g. "Bolivia").
"""

import json
import uuid

import requests
import streamlit as st
from app import API_BASE_URL, STREAMLIT_URL
from client import ZenoClient
from utils import render_dataset_map, render_stream

# Fixed dataset for this view: Forest Carbon Gross Removals
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
if "token" not in st.session_state:
    st.session_state["token"] = None

st.set_page_config(
    page_title="Map Chat - Zeno",
    page_icon="🌎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Chat column: own scroll, spacing from map
st.markdown(
    """
    <style>
    [data-testid="column"]:first-child {
        max-height: 85vh;
        overflow-y: auto;
        padding-right: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 30/70 split: chat left, map right
chat_col, map_col = st.columns([3, 7])

with chat_col:
    st.header("🐊")
    st.write(
        "Zeno's Uniguana is a friendly, knowledgeable guide to the Land and Carbon lab data."
    )
    st.caption("Ask about any place (e.g. Bolivia, Odisha) to zoom and highlight on the map.")

    if not st.session_state.get("token"):
        st.button(
            "Login with Global Forest Watch",
            key="login_map_chat",
            on_click=lambda: st.markdown(
                f'<meta http-equiv="refresh" content="0;url=https://api.resourcewatch.org/auth?callbackUrl={STREAMLIT_URL}&token=true">',
                unsafe_allow_html=True,
            ),
        )
    else:
        user_info = requests.get(
            f"{API_BASE_URL}/api/auth/me",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {st.session_state['token']}",
            },
        )
        if user_info.status_code == 200:
            st.session_state["user"] = user_info.json()
            st.success(f"Logged in as {st.session_state['user']['name']}")

    st.divider()

    # Chat history
    for message in st.session_state.map_chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    client = ZenoClient(
        base_url=API_BASE_URL, token=st.session_state.token
    )
    quota_info = client.get_quota_info()
    remaining_prompts = quota_info["promptQuota"] - quota_info["promptsUsed"]

    if "map_chat_pending_input" not in st.session_state:
        st.session_state.map_chat_pending_input = None

    def handle_map_chat_input():
        current = st.session_state.get("map_chat_user_input", "")
        if current and current.strip():
            st.session_state.map_chat_pending_input = current.strip()

    user_input = st.chat_input(
        f"Ask about a place... (remaining: {remaining_prompts})",
        key="map_chat_user_input",
        on_submit=handle_map_chat_input,
    )

    if st.session_state.map_chat_pending_input:
        user_input = st.session_state.map_chat_pending_input
        st.session_state.map_chat_pending_input = None

    if user_input and st.session_state.get("token"):
        st.session_state.map_chat_messages.append(
            {"role": "user", "content": user_input}
        )
        with st.chat_message("user"):
            st.markdown(user_input)

        ui_context = {
            "dataset_selected": {"dataset": FOREST_CARBON_REMOVALS_DATASET},
        }

        with st.chat_message("assistant"):
            for stream in client.chat(
                query=user_input,
                user_persona="Researcher",
                ui_context=ui_context,
                thread_id=st.session_state.map_chat_session_id,
                user_id=st.session_state.get("user", {}).get("email", "anonymous"),
            ):
                if stream.get("node") == "trace_info":
                    update = json.loads(stream["update"])
                    if "trace_id" in update:
                        st.success(f"🔍 Trace ID: {update['trace_id']}")
                    continue

                update = json.loads(stream["update"])

                if "aoi" in update:
                    st.session_state.map_aoi_data = update["aoi"]
                if "dataset" in update:
                    st.session_state.map_dataset_data = update["dataset"]

                render_stream(stream, skip_maps=True)

with map_col:
    if st.session_state.get("token"):
        render_dataset_map(
            st.session_state.map_dataset_data,
            st.session_state.map_aoi_data,
            show_title=True,
            width=1200,
            height=550,
        )
    else:
        st.info("Log in to view the map.")
