import json
import os
import time
import uuid

import streamlit as st
from utils import API_BASE_URL, render_dataset_map, render_stream
from zeno_client import ZenoClient

import src.shared.env  # noqa: F401
from constants import (
    DATA_SOURCES,
    FOREST_CARBON_REMOVALS_DATASET,
    SESSION_KEY_DATA_SOURCE,
    SESSION_KEY_MAP_AOI_DATA,
    SESSION_KEY_MAP_CHAT_MESSAGES,
    SESSION_KEY_MAP_CHAT_PENDING_INPUT,
    SESSION_KEY_MAP_CHAT_SESSION_ID,
    SESSION_KEY_MAP_CHAT_USER_INPUT,
    SESSION_KEY_MAP_DATASET_DATA,
    SESSION_KEY_MAP_JURISDICTION_BOUNDARY,
    SESSION_KEY_MAP_PROJECT_DATA,
    SESSION_KEY_MAP_PROJECT_LIST,
    SESSION_KEY_MAP_PROJECT_MATCHES,
    SESSION_KEY_TOKEN,
)
from src.shared.lake_county_constants import (
    LAKE_COUNTY_AOI,
    LAKE_COUNTY_LAYERS,
)

SHOW_RESPONSE_TIMER = True

LAKE_COUNTY_DEFAULT_LAYER = LAKE_COUNTY_LAYERS[1]  # areas

if SESSION_KEY_MAP_CHAT_SESSION_ID not in st.session_state:
    st.session_state[SESSION_KEY_MAP_CHAT_SESSION_ID] = str(uuid.uuid4())
if SESSION_KEY_MAP_CHAT_MESSAGES not in st.session_state:
    st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES] = []
if SESSION_KEY_MAP_AOI_DATA not in st.session_state:
    st.session_state[SESSION_KEY_MAP_AOI_DATA] = None
if SESSION_KEY_MAP_DATASET_DATA not in st.session_state:
    st.session_state[SESSION_KEY_MAP_DATASET_DATA] = FOREST_CARBON_REMOVALS_DATASET
if SESSION_KEY_MAP_PROJECT_DATA not in st.session_state:
    st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
if SESSION_KEY_MAP_PROJECT_MATCHES not in st.session_state:
    st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
if SESSION_KEY_MAP_PROJECT_LIST not in st.session_state:
    st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
if SESSION_KEY_MAP_JURISDICTION_BOUNDARY not in st.session_state:
    st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
if SESSION_KEY_DATA_SOURCE not in st.session_state:
    st.session_state[SESSION_KEY_DATA_SOURCE] = "forest_carbon"

token = st.query_params.get("token")
if token:
    st.session_state[SESSION_KEY_TOKEN] = token
    st.query_params.clear()

if SESSION_KEY_TOKEN not in st.session_state or st.session_state[SESSION_KEY_TOKEN] is None:
    auto_token = os.environ.get("AUTO_LOGIN_TOKEN")
    if auto_token and auto_token != "<your-gfw-jwt-token>":
        st.session_state[SESSION_KEY_TOKEN] = auto_token
    else:
        st.session_state[SESSION_KEY_TOKEN] = None

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
        index=0 if st.session_state[SESSION_KEY_DATA_SOURCE] == "forest_carbon" else 1,
        key="data_source_select",
    )
    ds_value = DATA_SOURCES[data_source]
    if ds_value != st.session_state[SESSION_KEY_DATA_SOURCE]:
        st.session_state[SESSION_KEY_DATA_SOURCE] = ds_value
        if ds_value == "lake_county":
            st.session_state[SESSION_KEY_MAP_DATASET_DATA] = LAKE_COUNTY_DEFAULT_LAYER
            st.session_state[SESSION_KEY_MAP_AOI_DATA] = LAKE_COUNTY_AOI
        else:
            st.session_state[SESSION_KEY_MAP_DATASET_DATA] = FOREST_CARBON_REMOVALS_DATASET
            st.session_state[SESSION_KEY_MAP_AOI_DATA] = None
            st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
            st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
            st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
            st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None

    if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county":
        st.caption("Search projects by name or filter by status, jurisdiction, or project type.")

    st.divider()

    for message in st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    client = ZenoClient(base_url=API_BASE_URL, token=st.session_state[SESSION_KEY_TOKEN])
    quota_info = client.get_quota_info()
    remaining_prompts = quota_info["promptQuota"] - quota_info["promptsUsed"]

    if SESSION_KEY_MAP_CHAT_PENDING_INPUT not in st.session_state:
        st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT] = None

    def handle_map_chat_input():
        current = st.session_state.get(SESSION_KEY_MAP_CHAT_USER_INPUT, "")
        if current and current.strip():
            st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT] = current.strip()

    placeholder = (
        "Search or filter Lake County projects"
        if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
        else "Ask about carbon removal for a location"
    )
    user_input = st.chat_input(
        f"{placeholder} (remaining: {remaining_prompts})",
        key=SESSION_KEY_MAP_CHAT_USER_INPUT,
        on_submit=handle_map_chat_input,
    )

    if st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT]:
        user_input = st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT]
        st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT] = None

    if user_input:
        st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        dataset = (
            st.session_state[SESSION_KEY_MAP_DATASET_DATA]
            if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
            else FOREST_CARBON_REMOVALS_DATASET
        )
        ui_context = {
            "data_source_selected": {"data_source": st.session_state[SESSION_KEY_DATA_SOURCE]},
            "dataset_selected": {"dataset": dataset},
            "aoi_selected": (
                {
                    "aoi": LAKE_COUNTY_AOI,
                    "aoi_name": "Lake County",
                    "subregion_aois": [],
                    "subregion": "",
                    "subtype": "",
                }
                if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
                else None
            ),
        }
        ui_context = {k: v for k, v in ui_context.items() if v is not None}

        with st.chat_message("assistant"):
            timer_placeholder = st.empty()
            progress_placeholder = st.empty()
            progress_placeholder.progress(0, text="Connecting...")
            start_time = time.perf_counter()
            stream_count = 0
            for stream in client.chat(
                query=user_input,
                user_persona="Researcher",
                ui_context=ui_context,
                thread_id=st.session_state[SESSION_KEY_MAP_CHAT_SESSION_ID],
                user_id=st.session_state.get("user", {}).get("email", "anonymous"),
            ):
                try:
                    if stream.get("node") == "trace_info":
                        continue
                    stream_count += 1
                    progress_placeholder.progress(
                        min(0.95, 0.05 + stream_count * 0.08),
                        text=f"Generating... ({stream_count} updates)",
                    )
                    update = json.loads(stream["update"])
                    if "aoi" in update:
                        st.session_state[SESSION_KEY_MAP_AOI_DATA] = update["aoi"]
                    if "dataset" in update:
                        st.session_state[SESSION_KEY_MAP_DATASET_DATA] = update["dataset"]
                    if "project_result" in update:
                        pr = update["project_result"]
                        if pr is None:
                            st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                            st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                            st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                            st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                        elif pr.get("list"):
                            st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = pr.get("matches", [])
                            st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = pr.get("jurisdiction_boundary")
                            st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                            st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                        elif pr.get("multiple"):
                            st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = pr.get("matches", [])
                            st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                            st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                            st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                        else:
                            st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = pr
                            st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                            st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                            st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                    elapsed = time.perf_counter() - start_time
                    if SHOW_RESPONSE_TIMER:
                        timer_placeholder.caption(f"Elapsed: {elapsed:.1f}s")
                    render_stream(stream, skip_maps=True)
                except Exception as e:
                    st.error(f"Error processing stream: {e}")
            progress_placeholder.empty()
            total_time = time.perf_counter() - start_time
            if SHOW_RESPONSE_TIMER:
                timer_placeholder.caption(f"Total response time: {total_time:.1f}s")

with map_col:
    if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county":
        matches = st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES]
        project_list = st.session_state[SESSION_KEY_MAP_PROJECT_LIST]
        if matches and not st.session_state[SESSION_KEY_MAP_PROJECT_DATA] and not project_list:
            st.write("**Select a project to view on the map:**")
            cols = st.columns(min(len(matches), 3))
            for i, m in enumerate(matches):
                name = m.get("attributes", {}).get("Name", f"Project {i + 1}")
                with cols[i % 3]:
                    if st.button(
                        name[:60] + ("..." if len(name) > 60 else ""),
                        key=f"lc_project_{i}",
                    ):
                        attrs = m.get("attributes", {})
                        st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = {
                            "rep_point_geojson": m.get("rep_point_geojson"),
                            "geometry_geojson": m.get("geometry_geojson"),
                            "geojson": m.get("geometry_geojson") or m.get("rep_point_geojson"),
                            "attributes": attrs,
                        }
                        st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                        detail_lines = [f"# {attrs.get('Name', name)}"]
                        for k, v in sorted(attrs.items()):
                            if v is not None and str(v).strip() and k not in ("OBJECTID", "GlobalID", "Shape__Area", "Shape__Length"):
                                label = k.replace("_", " ").title()
                                detail_lines.append(f"- **{label}:** {v}")
                        st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES].append(
                            {"role": "assistant", "content": "\n".join(detail_lines)}
                        )
                        st.rerun()
    render_dataset_map(
        st.session_state[SESSION_KEY_MAP_DATASET_DATA],
        st.session_state[SESSION_KEY_MAP_AOI_DATA],
        show_title=True,
        width=1200,
        height=550,
        project_data=st.session_state[SESSION_KEY_MAP_PROJECT_DATA]
        if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
        else None,
        project_list=st.session_state[SESSION_KEY_MAP_PROJECT_LIST]
        if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
        else None,
        jurisdiction_boundary=st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY]
        if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
        else None,
    )
