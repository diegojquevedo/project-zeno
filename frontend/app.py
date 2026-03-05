import json
import os
import time
import uuid
from collections import Counter
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components
from custom_renderer_registry import get_primary_action_types
from geo_map_renderer import render_geo_map
from streamlit_folium import folium_static
from utils import (
    API_BASE_URL,
    _fetch_lake_county_boundary_cached,
    render_charts,
    render_dataset_map,
    render_stream,
)
from zeno_client import ZenoClient

import src.shared.env  # noqa: F401
from constants import (
    DATA_SOURCES,
    FOREST_CARBON_REMOVALS_DATASET,
    SESSION_KEY_DATA_SOURCE,
    SESSION_KEY_GEO_RESULT_SUMMARY,
    SESSION_KEY_MAP_ACTIONS,
    SESSION_KEY_MAP_AOI_DATA,
    SESSION_KEY_MAP_CHARTS_DATA,
    SESSION_KEY_MAP_CHAT_MESSAGES,
    SESSION_KEY_MAP_CHAT_PENDING_INPUT,
    SESSION_KEY_MAP_CHAT_SESSION_ID,
    SESSION_KEY_MAP_CHAT_USER_INPUT,
    SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY,
    SESSION_KEY_MAP_DATASET_DATA,
    SESSION_KEY_MAP_JURISDICTION_BOUNDARY,
    SESSION_KEY_MAP_PROJECT_DATA,
    SESSION_KEY_MAP_PROJECT_LIST,
    SESSION_KEY_MAP_PROJECT_MATCHES,
    SESSION_KEY_TOKEN,
)
from src.api.geo_lake_county_config import GEO_LAKE_COUNTY_DEFAULT_LAYER
from src.shared.lake_county_constants import (
    LAKE_COUNTY_AOI,
    LAKE_COUNTY_LAYERS,
)

SHOW_RESPONSE_TIMER = True

LAKE_COUNTY_DEFAULT_LAYER = LAKE_COUNTY_LAYERS[1]


def _render_geo_result_summary(geo_summary: dict) -> None:
    total = geo_summary.get("total", 0)
    label = geo_summary.get("label_plural", "results")
    filters = geo_summary.get("filters", {})
    charts_data = geo_summary.get("charts_data", [])
    feature_rows = geo_summary.get("feature_rows", [])

    st.markdown(f"**Found {total} {label}**")

    filter_parts = []
    if filters.get("category") and filters["category"] != "projects":
        filter_parts.append(f"category: {filters['category']}")
    if filters.get("jurisdiction"):
        filter_parts.append(f"in {filters['jurisdiction']}")
    if filters.get("boundary"):
        filter_parts.append(f"in {filters['boundary']}")
    if filters.get("status"):
        filter_parts.append(f"status: {filters['status']}")
    if filter_parts:
        st.caption(" · ".join(filter_parts))

    _skip = {"OBJECTID", "GlobalID", "Shape__Area", "Shape__Length"}
    _date_columns = {"StartYear", "EndYear"}

    def _format_cell(key: str, val) -> str | object:
        if key not in _date_columns or val is None or val == "None":
            return val
        try:
            n = int(val)
            ts = n / 1000 if abs(n) > 1e10 else n
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m/%d/%Y")
        except (ValueError, TypeError, OSError):
            return val

    if total == 1 and feature_rows:
        st.divider()
        row = feature_rows[0]
        display_row = {k: _format_cell(k, v) for k, v in row.items() if k not in _skip}
        priority_keys = ("Name", "projecttype", "jurisdiction", "watershed", "subwatershed", "project_id")
        for key in priority_keys:
            if key in display_row and display_row[key] is not None:
                label_key = key.replace("_", " ").title()
                st.markdown(f"**{label_key}:** {display_row[key]}")
        remaining = {k: v for k, v in display_row.items() if k not in priority_keys and v is not None}
        if remaining:
            for k, v in remaining.items():
                st.caption(f"{k}: {v}")
    elif total > 1 and feature_rows:
        st.divider()
        summary_parts = []
        for row in feature_rows[:20]:
            name = row.get("Name") or row.get("project_id") or "Unnamed"
            ptype = row.get("projecttype")
            if ptype:
                summary_parts.append(f"• **{name}** ({ptype})")
            else:
                summary_parts.append(f"• **{name}**")
        if total > 20:
            summary_parts.append(f"_... and {total - 20} more_")
        st.markdown("\n".join(summary_parts))

    if charts_data:
        st.divider()
        render_charts(charts_data)

    if feature_rows and total > 0:
        st.divider()
        with st.expander(f"View full data ({total} {label})", expanded=(total == 1 or total <= 20)):
            display_rows = [
                {k: _format_cell(k, v) for k, v in row.items() if k not in _skip}
                for row in feature_rows
            ]
            st.dataframe(display_rows, use_container_width=True)

    st.divider()

if SESSION_KEY_MAP_CHAT_SESSION_ID not in st.session_state:
    st.session_state[SESSION_KEY_MAP_CHAT_SESSION_ID] = str(uuid.uuid4())
if SESSION_KEY_MAP_CHAT_MESSAGES not in st.session_state:
    st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES] = []
if SESSION_KEY_DATA_SOURCE not in st.session_state:
    st.session_state[SESSION_KEY_DATA_SOURCE] = "geo_lake_county"
if SESSION_KEY_MAP_AOI_DATA not in st.session_state:
    _ds = st.session_state.get(SESSION_KEY_DATA_SOURCE, "geo_lake_county")
    st.session_state[SESSION_KEY_MAP_AOI_DATA] = LAKE_COUNTY_AOI if _ds in ("geo_lake_county", "lake_county") else None
if SESSION_KEY_MAP_DATASET_DATA not in st.session_state:
    _ds = st.session_state.get(SESSION_KEY_DATA_SOURCE, "geo_lake_county")
    if _ds == "geo_lake_county":
        st.session_state[SESSION_KEY_MAP_DATASET_DATA] = GEO_LAKE_COUNTY_DEFAULT_LAYER
    elif _ds == "lake_county":
        st.session_state[SESSION_KEY_MAP_DATASET_DATA] = LAKE_COUNTY_DEFAULT_LAYER
    else:
        st.session_state[SESSION_KEY_MAP_DATASET_DATA] = FOREST_CARBON_REMOVALS_DATASET
if SESSION_KEY_MAP_PROJECT_DATA not in st.session_state:
    st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
if SESSION_KEY_MAP_PROJECT_MATCHES not in st.session_state:
    st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
if SESSION_KEY_MAP_PROJECT_LIST not in st.session_state:
    st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
if SESSION_KEY_MAP_CHARTS_DATA not in st.session_state:
    st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
if SESSION_KEY_MAP_JURISDICTION_BOUNDARY not in st.session_state:
    st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
if SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY not in st.session_state:
    st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = None
if SESSION_KEY_MAP_ACTIONS not in st.session_state:
    st.session_state[SESSION_KEY_MAP_ACTIONS] = []
if SESSION_KEY_GEO_RESULT_SUMMARY not in st.session_state:
    st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = None

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

    [data-testid="column"]:first-of-type { height: 85vh !important; max-height: 85vh !important; overflow: hidden !important; display: flex !important; flex-direction: column !important; }
    [data-testid="column"]:first-of-type > div { flex: 1 1 0 !important; min-height: 0 !important; overflow: hidden !important; display: flex !important; flex-direction: column !important; }
    [data-testid="column"]:first-of-type > div > *:nth-child(1) { flex-shrink: 0 !important; }
    [data-testid="column"]:first-of-type > div > *:nth-child(2) { flex: 1 1 0 !important; min-height: 0 !important; overflow-y: auto !important; overflow-x: hidden !important; -webkit-overflow-scrolling: touch !important; }
    [data-testid="column"]:first-of-type > div > [data-testid="stVerticalBlock"]:nth-of-type(2) { flex: 1 1 0 !important; min-height: 0 !important; overflow-y: auto !important; overflow-x: hidden !important; -webkit-overflow-scrolling: touch !important; max-height: 100% !important; }
    div.stHorizontalBlock > div:first-child { height: 85vh !important; max-height: 85vh !important; overflow: hidden !important; display: flex !important; flex-direction: column !important; }
    div.stHorizontalBlock > div:first-child > div { flex: 1 1 0 !important; min-height: 0 !important; overflow: hidden !important; display: flex !important; flex-direction: column !important; }
    div.stHorizontalBlock > div:first-child > div > div:nth-child(2) { flex: 1 1 0 !important; min-height: 0 !important; overflow-y: auto !important; overflow-x: hidden !important; -webkit-overflow-scrolling: touch !important; }
    [data-testid="column"]:first-of-type > div > *:nth-child(3) { flex-shrink: 0 !important; }
    [class*="geo_chat_header"] [data-testid="stHeader"],
    [class*="geo_chat_header"] h1 { margin-top: 0 !important; margin-bottom: 0.2rem !important; padding: 0 !important; }
    [class*="geo_chat_header"] [data-testid="stMarkdown"] { margin: 0 0 0.2rem 0 !important; }
    [class*="geo_chat_header"] [data-testid="stCaptionContainer"] { margin: 0 0 0.2rem 0 !important; }
    [class*="geo_chat_header"] [data-testid="stVerticalBlock"] > div { margin: 0 !important; padding: 0 !important; }
    [class*="geo_chat_header"] hr { margin: 0.25rem 0 !important; }
    [class*="st-key-data_source_selector"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

chat_col, map_col = st.columns([1, 1])

with chat_col:
    with st.container(key="geo_chat_header"):
        st.header("Geo AI")
        st.write("This is a friendly prompt-based system to filter and analyze mapping data.")

        with st.container(key="data_source_selector"):
            _ds_idx = list(DATA_SOURCES.values()).index(
                st.session_state[SESSION_KEY_DATA_SOURCE]
            ) if st.session_state[SESSION_KEY_DATA_SOURCE] in DATA_SOURCES.values() else 0
            data_source = st.selectbox(
                "Data source",
                options=list(DATA_SOURCES.keys()),
                index=_ds_idx,
                key="data_source_select",
            )
            ds_value = DATA_SOURCES[data_source]
            if ds_value != st.session_state[SESSION_KEY_DATA_SOURCE]:
                st.session_state[SESSION_KEY_DATA_SOURCE] = ds_value
                if ds_value == "lake_county":
                    st.session_state[SESSION_KEY_MAP_DATASET_DATA] = LAKE_COUNTY_DEFAULT_LAYER
                    st.session_state[SESSION_KEY_MAP_AOI_DATA] = LAKE_COUNTY_AOI
                elif ds_value == "geo_lake_county":
                    st.session_state[SESSION_KEY_MAP_DATASET_DATA] = GEO_LAKE_COUNTY_DEFAULT_LAYER
                    st.session_state[SESSION_KEY_MAP_AOI_DATA] = LAKE_COUNTY_AOI
                    st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                    st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                    st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                    st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
                    st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                    st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = None
                    st.session_state[SESSION_KEY_MAP_ACTIONS] = []
                else:
                    st.session_state[SESSION_KEY_MAP_DATASET_DATA] = FOREST_CARBON_REMOVALS_DATASET
                    st.session_state[SESSION_KEY_MAP_AOI_DATA] = None
                    st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                    st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                    st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                    st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
                    st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                    st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = None

            if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county":
                st.caption("Search projects by name or filter by status, jurisdiction, or project type.")

        st.divider()

    pending_input = st.session_state.pop(SESSION_KEY_MAP_CHAT_PENDING_INPUT, None)
    if pending_input:
        st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES].append({"role": "user", "content": pending_input})

    messages = st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES]

    with st.container(height=600, key="geo_chat_history", border=False):
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county":
            project_list = st.session_state.get(SESSION_KEY_MAP_PROJECT_LIST)
            charts_data = st.session_state.get(SESSION_KEY_MAP_CHARTS_DATA)
            if project_list and isinstance(project_list, list) and len(project_list) > 0:
                n = len(project_list)
                by_type = Counter(
                    m.get("attributes", {}).get("projecttype") or "(blank)"
                    for m in project_list
                )
                top_types = ", ".join(f"{c} {t}" for t, c in by_type.most_common(5))
                st.markdown(f"**Found {n} project{'s' if n != 1 else ''}**")
                if top_types:
                    st.caption(f"By type: {top_types}")
                if charts_data and isinstance(charts_data, list):
                    st.divider()
                    render_charts(charts_data)
                st.divider()

        if st.session_state[SESSION_KEY_DATA_SOURCE] == "geo_lake_county":
            geo_summary = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
            if geo_summary and isinstance(geo_summary, dict):
                _render_geo_result_summary(geo_summary)

        if pending_input:
            client = ZenoClient(base_url=API_BASE_URL, token=st.session_state[SESSION_KEY_TOKEN])
            dataset = (
                st.session_state[SESSION_KEY_MAP_DATASET_DATA]
                if st.session_state[SESSION_KEY_DATA_SOURCE] in ("lake_county", "geo_lake_county")
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
                    if st.session_state[SESSION_KEY_DATA_SOURCE] in ("lake_county", "geo_lake_county")
                    else None
                ),
            }
            ui_context = {k: v for k, v in ui_context.items() if v is not None}

            with st.chat_message("assistant"):
                timer_placeholder = st.empty()
                progress_placeholder = st.empty()
                geo_summary_placeholder = st.empty()
                progress_placeholder.progress(0, text="Connecting...")
                start_time = time.perf_counter()
                stream_count = 0
                last_tool_content = [None]
                for stream in client.chat(
                    query=pending_input,
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
                        if "geo_result_summary" in update and update["geo_result_summary"] is not None:
                            st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = update["geo_result_summary"]
                        if "map_actions" in update:
                            incoming = update["map_actions"]
                            existing = st.session_state.get(SESSION_KEY_MAP_ACTIONS, [])
                            primary_types = {"addFeatureLayer"} | get_primary_action_types()
                            is_primary_result = any(a.get("type") in primary_types for a in incoming)
                            if is_primary_result:
                                st.session_state[SESSION_KEY_MAP_ACTIONS] = incoming
                                if "geo_result_summary" not in update:
                                    st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = None
                            else:
                                st.session_state[SESSION_KEY_MAP_ACTIONS] = existing + incoming
                        if "project_result" in update:
                            pr = update["project_result"]
                            if pr is None:
                                st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                                st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                                st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                                st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
                                st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                                st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = None
                            elif pr.get("list"):
                                st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = pr.get("matches", [])
                                st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = pr.get("jurisdiction_boundary")
                                st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = (
                                    pr.get("district_boundary") or pr.get("county_board_district_boundary")
                                )
                                st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                                st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                                if update.get("charts_data"):
                                    st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = update["charts_data"]
                            elif pr.get("multiple"):
                                st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = pr.get("matches", [])
                                st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                                st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                                st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
                                st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                                st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = None
                            else:
                                st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = pr
                                st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                                st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                                st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
                                st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                                st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = (
                                    pr.get("district_boundary") or pr.get("county_board_district_boundary")
                                )
                        for msg in update.get("messages") or []:
                            if msg.get("kwargs", {}).get("type") == "tool" and msg.get("kwargs", {}).get("content"):
                                last_tool_content[0] = msg["kwargs"]["content"]
                        elapsed = time.perf_counter() - start_time
                        if SHOW_RESPONSE_TIMER:
                            timer_placeholder.caption(f"Elapsed: {elapsed:.1f}s")
                        render_stream(stream, skip_maps=True, stream_idx=stream_count)
                    except Exception as e:
                        st.error(f"Error processing stream: {e}")
                if last_tool_content[0]:
                    chat_msgs = st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES]
                    if chat_msgs and chat_msgs[-1].get("role") == "user":
                        st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES].append(
                            {"role": "assistant", "content": last_tool_content[0]}
                        )
                progress_placeholder.empty()
                total_time = time.perf_counter() - start_time
                if SHOW_RESPONSE_TIMER:
                    timer_placeholder.caption(f"Total response time: {total_time:.1f}s")
                geo_summary = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
                if geo_summary and isinstance(geo_summary, dict):
                    with geo_summary_placeholder.container():
                        _render_geo_result_summary(geo_summary)

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
        else "Ask about soils in a jurisdiction or jurisdictions with a soil type"
        if st.session_state[SESSION_KEY_DATA_SOURCE] == "geo_lake_county"
        else "Ask about carbon removal for a location"
    )
    st.chat_input(
        f"{placeholder} (remaining: {remaining_prompts})",
        key=SESSION_KEY_MAP_CHAT_USER_INPUT,
        on_submit=handle_map_chat_input,
    )

    _scroll_chat_to_bottom_js = """
    (function() {
        var doc = null;
        try { doc = window.parent.document; } catch (e) { return; }
        function findScrollable(el) {
            if (!el) return null;
            try {
                var s = window.parent.getComputedStyle(el);
                if (s.overflowY === 'auto' || s.overflowY === 'scroll') return el;
            } catch (e) {}
            for (var i = 0; i < (el.children || []).length; i++) {
                var c = findScrollable(el.children[i]);
                if (c) return c;
            }
            return null;
        }
        function getContainer() {
            var c = doc.querySelector('[class*="st-key-geo_chat_history"]') || doc.querySelector('[class*="geo_chat_history"]');
            if (c) return findScrollable(c) || c;
            return null;
        }
        function scrollToBottom() {
            var el = getContainer();
            if (el) el.scrollTop = el.scrollHeight;
        }
        var rafId = null;
        function isInsideExpander(node) {
            if (!node || !node.closest) return false;
            return !!(node.closest('[data-testid="stExpander"]') || node.closest('[class*="streamlit-expander"]') || node.closest('[class*="stExpander"]'));
        }
        function scheduleScroll(mutations) {
            for (var i = 0; i < (mutations && mutations.length) || 0; i++) {
                var m = mutations[i];
                if (isInsideExpander(m.target)) return;
            }
            if (rafId) return;
            rafId = window.parent.requestAnimationFrame(function() {
                rafId = null;
                scrollToBottom();
            });
        }
        var attempts = 0;
        function init() {
            var el = getContainer();
            if (!el && attempts < 60) {
                attempts++;
                window.parent.requestAnimationFrame(init);
                return;
            }
            scrollToBottom();
            if (el) {
                var obs = new MutationObserver(scheduleScroll);
                obs.observe(el, { childList: true, subtree: true });
            }
        }
        window.parent.requestAnimationFrame(init);
    })();
    """
    components.html(
        f"<script>{_scroll_chat_to_bottom_js}</script>",
        height=0,
    )

with map_col:
    if st.session_state[SESSION_KEY_DATA_SOURCE] == "geo_lake_county":
        map_actions = st.session_state.get(SESSION_KEY_MAP_ACTIONS, [])
        if map_actions and len(map_actions) > 0:
            lc_boundary = _fetch_lake_county_boundary_cached(
                API_BASE_URL, st.session_state.get(SESSION_KEY_TOKEN)
            )
            augmented_actions = list(map_actions)
            if lc_boundary and lc_boundary.get("features"):
                augmented_actions.insert(
                    0,
                    {
                        "type": "addBoundaryLayer",
                        "geojson": lc_boundary,
                        "label": "Lake County Boundary",
                    },
                )
            st.subheader("Geo AI")
            geo_map = render_geo_map(augmented_actions, width=1200, height=550)
            if geo_map:
                folium_static(geo_map, width=1200, height=550)
        else:
            render_dataset_map(
                st.session_state[SESSION_KEY_MAP_DATASET_DATA],
                st.session_state[SESSION_KEY_MAP_AOI_DATA],
                show_title=True,
                width=1200,
                height=550,
            )
    elif st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county":
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
            project_data=st.session_state[SESSION_KEY_MAP_PROJECT_DATA],
            project_list=st.session_state[SESSION_KEY_MAP_PROJECT_LIST],
            jurisdiction_boundary=st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY],
            county_board_district_boundary=st.session_state.get(SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY),
        )
    else:
        render_dataset_map(
            st.session_state[SESSION_KEY_MAP_DATASET_DATA],
            st.session_state[SESSION_KEY_MAP_AOI_DATA],
            show_title=True,
            width=1200,
            height=550,
        )
