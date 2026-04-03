import json
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components
from custom_renderer_registry import get_primary_action_types
from geo_map_project_table import (
    prepend_focus_zoom_if_any,
    render_geo_map_bottom_table,
)
from geo_map_renderer import (
    active_basemap_id_from_map_actions,
    merge_persist_basemap_into_actions,
    render_geo_map,
)
from main_header import render_main_header
from map_chat_pdf_export import (
    _split_project_attributes_from_text,
    _strip_md,
    build_map_chat_pdf_bytes,
)
from streamlit_folium import st_folium
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
    FOLIUM_STATIC_DEFAULT_HEIGHT,
    FOLIUM_STATIC_DEFAULT_WIDTH,
    FOREST_CARBON_REMOVALS_DATASET,
    GEO_CHAT_DEFER_TOOL_MESSAGE_TOOLS,
    GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER,
    GEO_CHAT_HISTORY_CONTAINER_MIN_HEIGHT_PX,
    GEO_CHAT_HISTORY_STREAMLIT_SCROLL_HEIGHT_PX,
    GEO_CHAT_PLACEHOLDER_FOREST_LONG,
    GEO_CHAT_PLACEHOLDER_GEO_LAKE_COUNTY_LONG,
    GEO_CHAT_PLACEHOLDER_LAKE_COUNTY_LONG,
    GEO_CHAT_PLACEHOLDER_SHORT,
    GEO_MAIN_COL_CHAT_MIN_HEIGHT_PX,
    GEO_MAP_CHAT_MAP_COLUMN_WEIGHTS,
    GEO_MAP_CHAT_MAP_COLUMNS_GAP,
    GEO_MAP_IFRAME_HOST_RIGHT_COL_SEL,
    GEO_MAP_SPLIT_CHAT_INPUT_FOOTER_MIN_HEIGHT,
    GEO_MAP_SPLIT_CHAT_INPUT_FOOTER_PADDING,
    GEO_MAP_SPLIT_CHAT_INPUT_SHELL_MIN_HEIGHT,
    GEO_MAP_SPLIT_MARGIN_BOTTOM_PX,
    GEO_MAP_SPLIT_MARGIN_TOP_PX,
    GEO_MAP_ST_HEADER_REM,
    GEO_MAP_STREAMLIT_KEY_CHAT_MAP_SPLIT,
    GEO_MAP_STREAMLIT_KEY_IFRAME_HOST,
    GEO_NARRATIVE_SUGGESTIONS_DELIM,
    MAP_CHAT_PDF,
    SESSION_KEY_DATA_SOURCE,
    SESSION_KEY_GEO_LAST_PROJECT_TOOL_TEXT,
    SESSION_KEY_GEO_MAP_TABLE_EXPANDED,
    SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW,
    SESSION_KEY_GEO_RESULT_SUMMARY,
    SESSION_KEY_GEO_SCHEMA_EXPORT_SNAPSHOT,
    SESSION_KEY_GEO_STREAM_SCHEMA_SHOWN,
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
    STREAMLIT_DEBUG_GEO_MAP_ENV,
    build_geo_map_column_css,
    build_map_chat_input_css,
)
from src.api.geo_lake_county_config import GEO_LAKE_COUNTY_DEFAULT_LAYER
from src.shared.lake_county_constants import (
    LAKE_COUNTY_AOI,
    LAKE_COUNTY_LAYERS,
)

SHOW_RESPONSE_TIMER = True

LAKE_COUNTY_DEFAULT_LAYER = LAKE_COUNTY_LAYERS[1]


def _format_geo_suggestions_for_display(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if len(lines) > 1:
        out: list[str] = []
        for ln in lines:
            if ln.startswith("- "):
                out.append(ln)
            elif ln.startswith(("* ", "• ")):
                out.append(f"- {ln[2:].strip()}")
            else:
                out.append(f"- {ln}")
        return "\n".join(out)
    block = lines[0] if lines else t
    if block.startswith("- "):
        return block
    if block.startswith("* "):
        return f"- {block[2:].strip()}"
    if block.startswith("• "):
        return f"- {block[2:].strip()}"
    pieces = re.split(r"(?<=[?.])\s+", block)
    pieces = [p.strip() for p in pieces if p.strip()]
    if len(pieces) <= 1:
        return f"- {block}"
    return "\n".join(f"- {p}" for p in pieces)


def _split_geo_narrative_for_display(full: str) -> tuple[str, str]:
    t = (full or "").strip()
    if not t:
        return "", ""
    d = GEO_NARRATIVE_SUGGESTIONS_DELIM
    i = t.find(d)
    if i >= 0:
        return t[:i].strip(), t[i + len(d) :].strip()
    m = re.search(
        r"(?i)\n+(?:Here are some (?:follow-up )?suggestions(?: for further exploration)?|Follow-up suggestions)\s*:?\s*\n",
        t,
    )
    if m:
        return t[: m.start()].strip(), t[m.end() :].strip()
    return t, ""


def _supplemental_project_attr_rows() -> list[tuple[str, str]] | None:
    raw = st.session_state.get(SESSION_KEY_GEO_LAST_PROJECT_TOOL_TEXT)
    if not raw or not isinstance(raw, str):
        return None
    _, rows, _ = _split_project_attributes_from_text(raw.strip())
    return rows if rows else None


def _render_geo_assistant_narrative_blocks(
    summary_part: str,
    suggestions_part: str,
    geo_summary: dict | None,
    *,
    show_structured: bool,
    supplemental_attr_rows: list[tuple[str, str]] | None = None,
) -> None:
    intro, attr_rows, attr_tail = _split_project_attributes_from_text(
        (summary_part or "").strip(),
    )
    if supplemental_attr_rows and len(attr_rows) == 0:
        attr_rows = list(supplemental_attr_rows)
    has_attrs = len(attr_rows) > 0
    summary_body = intro if has_attrs else (summary_part or "")

    if has_attrs:
        st.markdown(f"### {MAP_CHAT_PDF.SECTION.INDIVIDUAL_PROJECT_RESULTS_DETAIL}")
        st.markdown(f"#### {MAP_CHAT_PDF.SECTION.PROJECT_ATTRIBUTES}")
        for k, v in attr_rows:
            st.markdown(f"- **{k}:** {v}")
        if attr_tail.strip():
            st.caption(_strip_md(attr_tail.strip()))

    if summary_body.strip():
        st.markdown("### Summary")
        st.markdown(summary_body)

    if show_structured and geo_summary and isinstance(geo_summary, dict):
        _render_geo_result_summary(geo_summary)
    if suggestions_part:
        st.markdown("### Follow-up suggestions")
        st.markdown(_format_geo_suggestions_for_display(suggestions_part))


def _render_geo_result_summary(geo_summary: dict) -> None:
    st.markdown("### Results detail")
    total = geo_summary.get("total", 0)
    label = geo_summary.get("label_plural", "results")
    filters = geo_summary.get("filters", {})
    charts_data = geo_summary.get("charts_data", [])
    feature_rows = geo_summary.get("feature_rows", [])

    st.markdown(f"**Found {total} {label}**")
    if total > 0 and len(feature_rows) < total:
        st.caption(
            f"Showing {len(feature_rows)} of {total} in this panel; the map includes all {total}."
        )

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

    ne = geo_summary.get("narrative_enrichment")
    if ne and str(ne).strip():
        st.markdown("**Rich context**")
        st.markdown(str(ne).strip())

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
        st.markdown("**Record detail**")
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
        st.markdown("**Project list**")
        list_lines: list[str] = []
        for row in feature_rows[:20]:
            name = row.get("Name") or row.get("project_id") or "Unnamed"
            ptype = row.get("projecttype")
            if ptype:
                list_lines.append(f"- **{name}** ({ptype})")
            else:
                list_lines.append(f"- **{name}**")
        if total > 20:
            list_lines.append(f"- *… and {total - 20} more*")
        st.markdown("\n".join(list_lines))

    if feature_rows and total > 0:
        st.markdown("### Full results table")
        with st.expander(f"Open table ({total} {label})", expanded=(total == 1 or total <= 20)):
            display_rows = [
                {k: _format_cell(k, v) for k, v in row.items() if k not in _skip}
                for row in feature_rows
            ]
            st.dataframe(display_rows, use_container_width=True)

    if charts_data:
        render_charts(charts_data)

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
if SESSION_KEY_GEO_MAP_TABLE_EXPANDED not in st.session_state:
    st.session_state[SESSION_KEY_GEO_MAP_TABLE_EXPANDED] = True

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
    page_title="Geo AI",
    page_icon="🌎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_main_header()

_GEO_SPLIT_USABLE_HEIGHT = (
    f"calc(100vh - {GEO_MAP_ST_HEADER_REM} - {GEO_MAP_SPLIT_MARGIN_TOP_PX}px - {GEO_MAP_SPLIT_MARGIN_BOTTOM_PX}px)"
)

_APP_MAP_IFRAME_HOST_SEL = GEO_MAP_IFRAME_HOST_RIGHT_COL_SEL

_APP_CHAT_LEFT_STRETCH_CSS = """
    [class*="geo-chat-map-split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:has([class*="st-key-geo_main_col_chat"]) {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: 100% !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_chat"]) {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: 100% !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stElementContainer"]:not(:has([class*="st-key-geo_main_col_chat"])) {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:not(:has([class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > [data-testid="stVerticalBlock"]:not(:has([class*="st-key-geo_main_col_chat"])) {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"])),
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"])),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"])),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"])) {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: none !important;
        height: 100% !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"]),
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_main_col_chat"]) {
        min-height: __GEO_MAIN_COL_MIN_PX__px !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
        max-height: none !important;
        height: 100% !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: none !important;
        height: 100% !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
        padding-bottom: 0 !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child,
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
        gap: 0.4rem !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:not(:only-child),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:not(:only-child) {
        flex: 0 0 auto !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
        gap: 0.4rem !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:not(:only-child):has([class*="st-key-geo_chat_history"]),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:not(:only-child):has([class*="st-key-geo_chat_history"]),
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:not(:only-child)[class*="st-key-geo_chat_history"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:not(:only-child)[class*="st-key-geo_chat_history"] {
        flex: 1 1 0 !important;
        flex-grow: 1 !important;
        flex-shrink: 1 !important;
        min-height: __GCH_MIN_PX__px !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"] {
        flex: 1 1 0 !important;
        flex-grow: 1 !important;
        flex-shrink: 1 !important;
        min-height: __GCH_MIN_PX__px !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
        -webkit-overflow-scrolling: touch !important;
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(> [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(> [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]) {
        flex: 1 1 0 !important;
        flex-grow: 1 !important;
        flex-shrink: 1 !important;
        min-height: __GCH_MIN_PX__px !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(> [data-testid="stVerticalBlock"][class*="st-key-geo_chat_header"]),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(> [data-testid="stVerticalBlock"][class*="st-key-geo_chat_header"]) {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
    }
    [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div > [data-testid="stElementContainer"] {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"]:has([class*="st-key-geo_chat_header"]),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"]:has([class*="st-key-geo_chat_header"]) {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
        align-self: stretch !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"]:has([class*="st-key-geo_chat_history"]),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"]:has([class*="st-key-geo_chat_history"]) {
        flex: 1 1 0 !important;
        flex-shrink: 1 !important;
        min-height: __GCH_MIN_PX__px !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
        align-self: stretch !important;
        min-width: 0 !important;
    }
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"]:has([data-testid="stChatInput"]),
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map_chat_user_input"],
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map-chat-user-input"],
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map_chat_export_pdf"],
    [class*="geo-chat-map-split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map-chat-export-pdf"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"]:has([data-testid="stChatInput"]),
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map_chat_user_input"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map-chat-user-input"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map_chat_export_pdf"],
    [class*="geo_chat_map_split"] [class*="st-key-geo_main_col_chat"][data-testid="stVerticalBlock"] > div:only-child > [data-testid="stElementContainer"][class*="st-key-map-chat-export-pdf"] {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        align-self: stretch !important;
    }
    [class*="st-key-geo_chat_header"][data-testid="stVerticalBlock"],
    [class*="st-key-geo_chat_header"] [data-testid="stVerticalBlock"] {
        gap: 0.3rem !important;
    }
    [class*="st-key-geo_main_col_chat"] [class*="st-key-geo_chat_header"],
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"]:has([class*="st-key-geo_chat_header"]) {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
    }
    [class*="st-key-geo_main_col_chat"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"] {
        flex: 1 1 0 !important;
        flex-shrink: 1 !important;
        min-height: __GCH_MIN_PX__px !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
        -webkit-overflow-scrolling: touch !important;
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"]:has([class*="st-key-geo_chat_history"]) {
        flex: 1 1 0 !important;
        flex-shrink: 1 !important;
        min-height: __GCH_MIN_PX__px !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    [class*="st-key-geo_chat_history"][data-testid="stVerticalBlock"] > div {
        flex: 0 0 auto !important;
        min-height: 0 !important;
        overflow: visible !important;
        align-items: stretch !important;
    }
    [class*="st-key-geo_chat_history"][data-testid="stVerticalBlock"] > div > [data-testid="stElementContainer"] {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        flex-grow: 0 !important;
        min-height: 0 !important;
    }
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"]:has([data-testid="stChatInput"]),
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"][class*="st-key-map_chat_user_input"],
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"][class*="st-key-map-chat-user-input"],
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"][class*="st-key-map_chat_export_pdf"],
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"][class*="st-key-map-chat-export-pdf"] {
        flex: 0 0 auto !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
""".replace(
    "__GCH_MIN_PX__",
    str(GEO_CHAT_HISTORY_CONTAINER_MIN_HEIGHT_PX),
).replace(
    "__GEO_MAIN_COL_MIN_PX__",
    str(GEO_MAIN_COL_CHAT_MIN_HEIGHT_PX),
)

st.markdown(
    f"""
    <style>
    main .block-container, .block-container {{ padding-top: {GEO_MAP_ST_HEADER_REM} !important; padding-bottom: 0 !important; overflow-x: hidden !important; overflow-y: auto !important; max-width: 100% !important; max-height: 100vh !important; box-sizing: border-box !important; gap: 0 !important; }}
    main .block-container > [data-testid="stVerticalBlock"],
    .block-container > [data-testid="stVerticalBlock"] {{ gap: 0 !important; padding-bottom: 0 !important; }}
    h1, h2, h3, [data-testid="stHeader"], [data-testid="stSubheader"] {{ overflow: visible !important; }}
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="collapsedControl"] {{ display: none !important; }}
    button[aria-label="Expand sidebar"],
    button[aria-label="Collapse sidebar"],
    [data-testid="stSidebarCollapsedButton"] {{ display: none !important; }}

    [class*="geo-chat-map-split"],
    [class*="geo_chat_map_split"] {{
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        height: {_GEO_SPLIT_USABLE_HEIGHT} !important;
        max-height: {_GEO_SPLIT_USABLE_HEIGHT} !important;
        min-height: 0 !important;
        margin-top: {GEO_MAP_SPLIT_MARGIN_TOP_PX}px !important;
        box-sizing: border-box !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        overflow: visible !important;
        gap: 0 !important;
        padding: 0 !important;
    }}
    [class*="geo-chat-map-split"] > [data-testid="stElementContainer"]:has(iframe),
    [class*="geo_chat_map_split"] > [data-testid="stElementContainer"]:has(iframe) {{
        height: 0 !important;
        max-height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: hidden !important;
        border: none !important;
        visibility: hidden !important;
        flex: 0 0 0 !important;
        line-height: 0 !important;
    }}
    [class*="geo-chat-map-split"] > [data-testid="stElementContainer"]:has(iframe) iframe,
    [class*="geo_chat_map_split"] > [data-testid="stElementContainer"]:has(iframe) iframe {{
        width: 1px !important;
        height: 1px !important;
        max-height: 1px !important;
        border: none !important;
        opacity: 0 !important;
        display: block !important;
        pointer-events: none !important;
    }}
    [class*="geo-chat-map-split"] > div,
    [class*="geo_chat_map_split"] > div {{
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: 100% !important;
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: stretch !important;
        overflow: visible !important;
        padding: 0 !important;
    }}
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"],
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: 100% !important;
        height: 100% !important;
        align-items: stretch !important;
        overflow: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"],
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
        min-height: 0 !important;
        max-height: 100% !important;
        height: 100% !important;
        align-items: stretch !important;
        overflow: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) {{
        max-height: 100% !important;
        min-height: 0 !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        padding-bottom: 0 !important;
        box-sizing: border-box !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div,
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div,
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div,
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div,
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div,
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(1),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(1),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(1),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(1),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(1),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(1) {{
        flex-shrink: 0 !important;
        overflow: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(2),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(2),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(2),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(2),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(2),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(2) {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        overflow-y: visible !important;
        overflow-x: hidden !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(3),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(3),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(3),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(3),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(3),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) > div > *:nth-child(3) {{
        flex-shrink: 0 !important;
    }}
    """
    + _APP_CHAT_LEFT_STRETCH_CSS
    + f"""
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) {{
        max-height: 100% !important;
        min-height: 0 !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        overflow-x: hidden !important;
        overflow-y: hidden !important;
        box-sizing: border-box !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div,
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div,
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div,
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div,
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div,
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stVerticalBlock"],
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stVerticalBlock"],
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stVerticalBlock"],
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stVerticalBlock"],
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stVerticalBlock"],
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stVerticalBlock"] {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) > div > [data-testid="stElementContainer"]:has([class*="st-key-geo_main_col_map"]) {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-geo_main_col_map"]),
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-geo_main_col_map"]) {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlock"][class*="st-key-geo_main_col_map"],
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlock"][class*="st-key-geo_main_col_map"],
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlock"][class*="st-key-geo_main_col_map"],
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlock"][class*="st-key-geo_main_col_map"],
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlock"][class*="st-key-geo_main_col_map"],
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stVerticalBlock"][class*="st-key-geo_main_col_map"] {{
        flex: 1 1 0 !important;
        min-height: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }}
    {_APP_MAP_IFRAME_HOST_SEL} {{ flex: 1 1 0 !important; min-height: 0 !important; overflow: hidden !important; margin-bottom: 0; padding-bottom: 0; display: flex; flex-direction: column; }}
    [class*="st-key-geo_map_table_debug_wrap"] {{ flex: 0 0 auto !important; flex-shrink: 0 !important; min-height: 0 !important; }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"],
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"],
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"],
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"],
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"],
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] {{
        flex: 0 0 auto !important;
        height: auto !important;
        min-height: 0 !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] > div,
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] > div,
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] > div,
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] > div,
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] > div,
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stHorizontalBlock"] > div {{
        flex: 0 0 auto !important;
        height: auto !important;
        min-height: 0 !important;
        overflow: visible !important;
    }}
    [class*="geo-chat-map-split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stColumn"],
    [class*="geo-chat-map-split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stColumn"],
    [class*="geo_chat_map_split"] > div > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stColumn"],
    [class*="geo_chat_map_split"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stColumn"],
    [class*="geo-chat-map-split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stColumn"],
    [class*="geo_chat_map_split"] > div > :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) [data-testid="stColumn"] {{
        height: auto !important;
        min-height: 0 !important;
    }}
    [class*="geo_chat_header"] {{ overflow: visible !important; }}
    [class*="geo_chat_header"] [data-testid="stHeader"],
    [class*="geo_chat_header"] h1 {{ margin-top: 0 !important; margin-bottom: 0.2rem !important; padding: 0 !important; }}
    [class*="geo_chat_header"] [data-testid="stMarkdown"] {{ margin: 0 0 0.2rem 0 !important; }}
    [class*="geo_chat_header"] [data-testid="stCaptionContainer"] {{ margin: 0 0 0.2rem 0 !important; }}
    [class*="geo_chat_header"] [data-testid="stVerticalBlock"] > div {{ margin: 0 !important; }}
    [class*="geo_chat_header"] hr {{ margin: 0.25rem 0 !important; }}
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"][class*="st-key-data_source_select"],
    [class*="st-key-geo_main_col_chat"] [data-testid="stElementContainer"]:has([class*="st-key-data_source_select"]) {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }}
    """
    + build_map_chat_input_css()
    + f"""
    [class*="st-key-geo_main_col_chat"] [data-testid="stChatInputContainer"],
    [class*="st-key-geo_main_col_chat"] .stChatFloatingInputContainer {{
        margin: 0 !important;
        padding-bottom: 0 !important;
        height: auto !important;
        min-height: 0 !important;
    }}
    [class*="st-key-geo_main_col_chat"] [data-testid="stChatInputContainer"] > *,
    [class*="st-key-geo_main_col_chat"] .stChatFloatingInputContainer > * {{
        margin-bottom: 0 !important;
    }}
    [class*="st-key-map_chat_user_input"],
    [class*="st-key-map-chat-user-input"] {{
        margin: 0 !important;
        padding: 0 !important;
        height: fit-content !important;
        max-height: none !important;
    }}
    [class*="st-key-geo_main_col_chat"] [data-testid="stChatInput"] {{
        height: auto !important;
        min-height: 0 !important;
    }}
    [class*="st-key-geo_main_col_chat"] [data-testid="stChatInput"] > div {{
        min-height: {GEO_MAP_SPLIT_CHAT_INPUT_SHELL_MIN_HEIGHT} !important;
        height: auto !important;
    }}
    [class*="st-key-geo_main_col_chat"] [data-testid="stChatInput"] > div > div:has([data-testid="InputInstructions"]) {{
        flex: 0 0 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    [class*="st-key-geo_main_col_chat"] [data-testid="stChatInput"] > div > div:has(button) {{
        min-height: {GEO_MAP_SPLIT_CHAT_INPUT_FOOTER_MIN_HEIGHT} !important;
        padding: {GEO_MAP_SPLIT_CHAT_INPUT_FOOTER_PADDING} !important;
    }}
    """
    + build_geo_map_column_css()
    + """
    [data-testid="stChatMessageContent"] {
        margin: 0 !important;
    }
    [data-testid="stChatMessageContent"] > div {
        flex: 0 1 auto !important;
        flex-grow: 0 !important;
        min-height: 0 !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    [data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
        flex: 0 1 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stLayoutWrapper"]:has([data-testid="stChatMessage"]),
    [class*="geo_chat_map_split"] [data-testid="stLayoutWrapper"]:has([data-testid="stChatMessage"]) {
        flex: 0 0 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        height: fit-content !important;
        min-height: 0 !important;
        max-height: none !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        justify-content: flex-start !important;
        width: 100% !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stElementContainer"]:has([data-testid="stChatMessage"]),
    [class*="geo_chat_map_split"] [data-testid="stElementContainer"]:has([data-testid="stChatMessage"]) {
        flex: 0 0 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        height: auto !important;
        min-height: 0 !important;
        max-height: none !important;
        align-self: stretch !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stChatMessage"],
    [class*="geo_chat_map_split"] [data-testid="stChatMessage"] {
        flex: 0 0 auto !important;
        align-items: flex-start !important;
        align-content: flex-start !important;
        width: 100% !important;
        max-width: 100% !important;
        min-height: 0 !important;
        height: auto !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stChatMessage"] [data-testid="stChatMessageContent"],
    [class*="geo_chat_map_split"] [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
        margin: 0 !important;
        flex-grow: 1 !important;
        flex-shrink: 1 !important;
        flex-basis: auto !important;
        min-width: 0 !important;
        align-self: flex-start !important;
        height: auto !important;
        min-height: 0 !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] > div,
    [class*="geo_chat_map_split"] [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] > div {
        flex: 0 0 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        align-self: flex-start !important;
        height: auto !important;
        min-height: 0 !important;
        width: 100% !important;
    }
    [class*="st-key-geo_chat_history"] [data-testid="stChatMessage"] {
        flex: 0 0 auto !important;
        align-items: flex-start !important;
        width: 100% !important;
        min-height: 0 !important;
    }
    [class*="st-key-geo_chat_history"] [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
        margin: 0 !important;
        flex-grow: 1 !important;
        flex-shrink: 1 !important;
        flex-basis: auto !important;
        min-width: 0 !important;
        align-self: flex-start !important;
        height: auto !important;
        min-height: 0 !important;
    }
    [class*="st-key-geo_chat_history"] [data-testid="stChatMessage"] [data-testid="stLayoutWrapper"] {
        flex: 0 0 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        height: fit-content !important;
        max-height: none !important;
        min-height: 0 !important;
        align-self: flex-start !important;
    }
    [class*="st-key-geo_chat_history"] [data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {
        flex: 0 0 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        min-height: 0 !important;
    }
    [class*="st-key-geo_chat_history"] [data-testid="stChatMessageContent"] > div {
        flex: 0 0 auto !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        align-self: flex-start !important;
        height: auto !important;
        min-height: 0 !important;
        width: 100% !important;
    }
    [data-testid="stChatMessage"] h2,
    [data-testid="stChatMessage"] h3 {
        margin-top: 0.35rem !important;
        margin-bottom: 0.25rem !important;
    }
    [data-testid="stChatMessage"] [data-testid="stExpander"] {
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }
    [class*="st-key-geo_chat_schema_discovery"] {
        margin-top: 0 !important;
        margin-bottom: 0.15rem !important;
    }
    [class*="st-key-geo_chat_schema_discovery"] details {
        border-radius: 6px !important;
    }
    [class*="st-key-geo_chat_schema_discovery"] [data-testid="stExpander"] {
        margin-top: 0.08rem !important;
        margin-bottom: 0 !important;
    }
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]),
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]) {{
        overflow-y: auto !important;
        overflow-x: hidden !important;
        min-height: 0 !important;
        -webkit-overflow-scrolling: touch !important;
    }}
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"] > div,
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"] > div {{
        flex: 0 0 auto !important;
        min-height: 0 !important;
        max-height: none !important;
        overflow: visible !important;
    }}
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"],
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"] {{
        scrollbar-width: thin !important;
        scrollbar-color: rgba(49, 51, 63, 0.5) rgba(240, 242, 248, 1) !important;
    }}
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]::-webkit-scrollbar,
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]::-webkit-scrollbar {{
        width: 8px !important;
    }}
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]::-webkit-scrollbar-thumb,
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]::-webkit-scrollbar-thumb {{
        background: rgba(49, 51, 63, 0.35) !important;
        border-radius: 4px !important;
    }}
    [class*="geo-chat-map-split"] [data-testid="stVerticalBlock"][class*="st-key-geo_map_iframe_host"],
    [class*="geo_chat_map_split"] [data-testid="stVerticalBlock"][class*="st-key-geo_map_iframe_host"] {{
        box-sizing: border-box !important;
        height: auto !important;
        max-height: none !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key=GEO_MAP_STREAMLIT_KEY_CHAT_MAP_SPLIT):
    chat_col, map_col = st.columns(
        GEO_MAP_CHAT_MAP_COLUMN_WEIGHTS,
        gap=GEO_MAP_CHAT_MAP_COLUMNS_GAP,
    )

    with chat_col:
        with st.container(border=True, key="geo_main_col_chat"):
            with st.container(key="geo_chat_header"):
                st.markdown(
                    "<p>This is a friendly prompt-based system to filter and analyze mapping data.</p>"
                    '<div aria-hidden="true" style="border-top:1px solid rgba(49,51,63,0.22);margin:0.6rem 0 0.5rem 0;width:100%;"></div>',
                    unsafe_allow_html=True,
                )

                _ds_idx = list(DATA_SOURCES.values()).index(
                    st.session_state[SESSION_KEY_DATA_SOURCE]
                ) if st.session_state[SESSION_KEY_DATA_SOURCE] in DATA_SOURCES.values() else 0
                data_source = st.selectbox(
                    "Data source",
                    options=list(DATA_SOURCES.keys()),
                    index=_ds_idx,
                    key="data_source_select",
                    label_visibility="collapsed",
                )
                ds_value = DATA_SOURCES[data_source]
                if ds_value != st.session_state[SESSION_KEY_DATA_SOURCE]:
                    st.session_state[SESSION_KEY_DATA_SOURCE] = ds_value
                    if ds_value == "lake_county":
                        st.session_state[SESSION_KEY_MAP_DATASET_DATA] = LAKE_COUNTY_DEFAULT_LAYER
                        st.session_state[SESSION_KEY_MAP_AOI_DATA] = LAKE_COUNTY_AOI
                        st.session_state[SESSION_KEY_GEO_SCHEMA_EXPORT_SNAPSHOT] = None
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
                        st.session_state[SESSION_KEY_GEO_SCHEMA_EXPORT_SNAPSHOT] = None
                    else:
                        st.session_state[SESSION_KEY_MAP_DATASET_DATA] = FOREST_CARBON_REMOVALS_DATASET
                        st.session_state[SESSION_KEY_MAP_AOI_DATA] = None
                        st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                        st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                        st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                        st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = None
                        st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY] = None
                        st.session_state[SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY] = None
                        st.session_state[SESSION_KEY_GEO_SCHEMA_EXPORT_SNAPSHOT] = None

                if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county":
                    st.caption("Search projects by name or filter by status, jurisdiction, or project type.")

            pending_input = st.session_state.pop(SESSION_KEY_MAP_CHAT_PENDING_INPUT, None)
            if pending_input:
                st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES].append({"role": "user", "content": pending_input})

            messages = st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES]
            _is_geo_lc = st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county"

            with st.container(
                key="geo_chat_history",
                border=False,
                height=GEO_CHAT_HISTORY_STREAMLIT_SCROLL_HEIGHT_PX,
            ):
                rest_msgs = messages[:-1] if len(messages) > 1 else []
                last_msg = messages[-1] if messages else None
                for message in rest_msgs:
                    with st.chat_message(message["role"]):
                        st.markdown(message.get("content") or "")

                if last_msg:
                    with st.chat_message(last_msg["role"]):
                        if last_msg["role"] == "assistant" and _is_geo_lc:
                            raw = (last_msg.get("content") or "").strip()
                            geo_snap = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
                            if raw == GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER:
                                st.caption(raw)
                                if geo_snap and isinstance(geo_snap, dict):
                                    _render_geo_result_summary(geo_snap)
                            else:
                                sp, sug = _split_geo_narrative_for_display(raw)
                                _render_geo_assistant_narrative_blocks(
                                    sp,
                                    sug,
                                    geo_snap,
                                    show_structured=True,
                                    supplemental_attr_rows=_supplemental_project_attr_rows(),
                                )
                        else:
                            st.markdown(last_msg.get("content") or "")

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
                            render_charts(charts_data)

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
                    if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county":
                        ui_context["geo_lake_county_map_context"] = {
                            "active_basemap_id": active_basemap_id_from_map_actions(
                                st.session_state.get(SESSION_KEY_MAP_ACTIONS)
                            ),
                        }
                    ui_context = {k: v for k, v in ui_context.items() if v is not None}

                    geo_ai_buffer: list[str] = []
                    with st.chat_message("assistant"):
                        if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county":
                            st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = None
                            st.session_state[SESSION_KEY_GEO_MAP_TABLE_FOCUS_ROW] = None
                            st.session_state[SESSION_KEY_GEO_LAST_PROJECT_TOOL_TEXT] = None
                        st.session_state[SESSION_KEY_GEO_STREAM_SCHEMA_SHOWN] = False
                        timer_placeholder = st.empty()
                        progress_placeholder = st.empty()
                        progress_placeholder.progress(0, text="Connecting...")
                        start_time = time.perf_counter()
                        stream_count = 0
                        last_tool_content = [None]
                        last_tool_name = [None]
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
                                if stream.get("node") == "ui_state":
                                    update = json.loads(stream["update"])
                                    if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county":
                                        gs = update.get("geo_result_summary")
                                        if gs is not None:
                                            st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = gs
                                            if isinstance(gs, dict) and gs.get("charts_data"):
                                                st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = gs["charts_data"]
                                        ma = update.get("map_actions")
                                        if ma:
                                            prev_ma = st.session_state.get(SESSION_KEY_MAP_ACTIONS)
                                            st.session_state[SESSION_KEY_MAP_ACTIONS] = (
                                                merge_persist_basemap_into_actions(ma, prev_ma)
                                            )
                                        cd = update.get("charts_data")
                                        if cd:
                                            st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = cd
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
                                if "map_actions" in update:
                                    incoming = update["map_actions"]
                                    existing = st.session_state.get(SESSION_KEY_MAP_ACTIONS, [])
                                    primary_types = {"addFeatureLayer"} | get_primary_action_types()
                                    is_primary_result = any(
                                        a.get("type") in primary_types for a in (incoming or [])
                                    )
                                    if is_primary_result:
                                        if incoming:
                                            st.session_state[SESSION_KEY_MAP_ACTIONS] = (
                                                merge_persist_basemap_into_actions(incoming, existing)
                                            )
                                    else:
                                        st.session_state[SESSION_KEY_MAP_ACTIONS] = existing + (
                                            incoming or []
                                        )
                                if "geo_result_summary" in update:
                                    gs = update["geo_result_summary"]
                                    if gs is None:
                                        st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = None
                                    else:
                                        st.session_state[SESSION_KEY_GEO_RESULT_SUMMARY] = gs
                                        if (
                                            isinstance(gs, dict)
                                            and gs.get("charts_data")
                                            and st.session_state.get(SESSION_KEY_DATA_SOURCE)
                                            == "geo_lake_county"
                                        ):
                                            st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = gs["charts_data"]
                                if update.get("charts_data") and st.session_state.get(
                                    SESSION_KEY_DATA_SOURCE
                                ) == "geo_lake_county":
                                    st.session_state[SESSION_KEY_MAP_CHARTS_DATA] = update["charts_data"]
                                if (
                                    "project_result" in update
                                    and st.session_state.get(SESSION_KEY_DATA_SOURCE) != "geo_lake_county"
                                ):
                                    pr = update["project_result"]
                                    if pr is None:
                                        st.session_state[SESSION_KEY_MAP_PROJECT_DATA] = None
                                        st.session_state[SESSION_KEY_MAP_PROJECT_MATCHES] = None
                                        st.session_state[SESSION_KEY_MAP_PROJECT_LIST] = None
                                        if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "lake_county":
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
                                        last_tool_name[0] = msg["kwargs"].get("name")
                                        if (
                                            msg["kwargs"].get("name") == "geo_get_project_geometry"
                                            and st.session_state.get(SESSION_KEY_DATA_SOURCE)
                                            == "geo_lake_county"
                                        ):
                                            st.session_state[SESSION_KEY_GEO_LAST_PROJECT_TOOL_TEXT] = (
                                                msg["kwargs"]["content"]
                                            )
                                elapsed = time.perf_counter() - start_time
                                if SHOW_RESPONSE_TIMER:
                                    timer_placeholder.caption(f"Elapsed: {elapsed:.1f}s")
                                _defer_charts = (
                                    st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county"
                                )
                                _buf = geo_ai_buffer if _defer_charts else None
                                render_stream(
                                    stream,
                                    skip_maps=True,
                                    defer_stream_charts=_defer_charts,
                                    ai_text_buffer=_buf,
                                )
                            except Exception as e:
                                st.error(f"Error processing stream: {e}")
                        chat_msgs = st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES]
                        if chat_msgs and chat_msgs[-1].get("role") == "user":
                            geo_snap = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
                            combined_narrative = "\n\n".join(geo_ai_buffer).strip()
                            assistant_body = None
                            if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county":
                                if combined_narrative:
                                    assistant_body = combined_narrative
                                elif (
                                    geo_snap
                                    and isinstance(geo_snap, dict)
                                    and last_tool_name[0] in GEO_CHAT_DEFER_TOOL_MESSAGE_TOOLS
                                ):
                                    assistant_body = GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER
                                elif last_tool_content[0]:
                                    assistant_body = last_tool_content[0]
                                elif geo_snap and isinstance(geo_snap, dict):
                                    assistant_body = GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER
                            elif last_tool_content[0]:
                                if (
                                    st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
                                    and isinstance(st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY), dict)
                                    and last_tool_name[0] in GEO_CHAT_DEFER_TOOL_MESSAGE_TOOLS
                                ):
                                    assistant_body = GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER
                                else:
                                    assistant_body = last_tool_content[0]
                            if assistant_body:
                                st.session_state[SESSION_KEY_MAP_CHAT_MESSAGES].append(
                                    {"role": "assistant", "content": assistant_body}
                                )
                        progress_placeholder.empty()
                        total_time = time.perf_counter() - start_time
                        if SHOW_RESPONSE_TIMER:
                            timer_placeholder.caption(f"Total response time: {total_time:.1f}s")
                        geo_summary = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
                        if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county":
                            combined_live = "\n\n".join(geo_ai_buffer).strip()
                            if combined_live:
                                sp, sug = _split_geo_narrative_for_display(combined_live)
                                _render_geo_assistant_narrative_blocks(
                                    sp,
                                    sug,
                                    geo_summary,
                                    show_structured=True,
                                    supplemental_attr_rows=_supplemental_project_attr_rows(),
                                )
                            elif geo_summary and isinstance(geo_summary, dict):
                                _render_geo_result_summary(geo_summary)
                        elif geo_summary and isinstance(geo_summary, dict):
                            _render_geo_result_summary(geo_summary)

            _export_msgs = st.session_state.get(SESSION_KEY_MAP_CHAT_MESSAGES, [])
            if isinstance(_export_msgs, list) and any(
                isinstance(m, dict) and m.get("role") in ("user", "assistant") for m in _export_msgs
            ):
                _gs = st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY)
                _sch = st.session_state.get(SESSION_KEY_GEO_SCHEMA_EXPORT_SNAPSHOT)
                _ds_pdf = st.session_state.get(SESSION_KEY_DATA_SOURCE)
                _pdf_sup = _supplemental_project_attr_rows()
                _pdf_bytes = build_map_chat_pdf_bytes(
                    _export_msgs,
                    geo_summary=_gs if isinstance(_gs, dict) else None,
                    schema_snapshot=_sch if isinstance(_sch, dict) else None,
                    data_source=_ds_pdf if isinstance(_ds_pdf, str) else None,
                    supplemental_project_attributes=_pdf_sup,
                )
                st.download_button(
                    MAP_CHAT_PDF.EXPORT.LABEL,
                    data=_pdf_bytes,
                    file_name=f"{MAP_CHAT_PDF.EXPORT.FILENAME_PREFIX}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}UTC.pdf",
                    mime="application/pdf",
                    key="map_chat_export_pdf",
                    use_container_width=True,
                )

            if SESSION_KEY_MAP_CHAT_PENDING_INPUT not in st.session_state:
                st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT] = None

            def handle_map_chat_input():
                current = st.session_state.get(SESSION_KEY_MAP_CHAT_USER_INPUT, "")
                if current and current.strip():
                    st.session_state[SESSION_KEY_MAP_CHAT_PENDING_INPUT] = current.strip()

            _chat_msgs = st.session_state.get(SESSION_KEY_MAP_CHAT_MESSAGES, [])
            _user_has_prompted = any(
                isinstance(m, dict) and m.get("role") == "user" for m in _chat_msgs
            )
            if _user_has_prompted:
                _chat_placeholder = GEO_CHAT_PLACEHOLDER_SHORT
            else:
                _base_ph = (
                    GEO_CHAT_PLACEHOLDER_LAKE_COUNTY_LONG
                    if st.session_state[SESSION_KEY_DATA_SOURCE] == "lake_county"
                    else GEO_CHAT_PLACEHOLDER_GEO_LAKE_COUNTY_LONG
                    if st.session_state[SESSION_KEY_DATA_SOURCE] == "geo_lake_county"
                    else GEO_CHAT_PLACEHOLDER_FOREST_LONG
                )
                _chat_placeholder = _base_ph
            st.chat_input(
                _chat_placeholder,
                key=SESSION_KEY_MAP_CHAT_USER_INPUT,
                on_submit=handle_map_chat_input,
            )

    with map_col:
        with st.container(border=True, key="geo_main_col_map"):
            with st.container(key=GEO_MAP_STREAMLIT_KEY_IFRAME_HOST):
                if st.session_state[SESSION_KEY_DATA_SOURCE] == "geo_lake_county":
                    map_actions = st.session_state.get(SESSION_KEY_MAP_ACTIONS, [])
                    geo_map_height = FOLIUM_STATIC_DEFAULT_HEIGHT
                    if os.environ.get(STREAMLIT_DEBUG_GEO_MAP_ENV):
                        st.caption(
                            f"[debug] map_actions={len(map_actions)} "
                            f"geo_summary={'yes' if st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY) else 'no'}"
                        )
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
                        augmented_actions = prepend_focus_zoom_if_any(
                            augmented_actions,
                            map_actions,
                            st.session_state.get(SESSION_KEY_GEO_RESULT_SUMMARY),
                        )
                        geo_map = render_geo_map(
                            augmented_actions,
                            width=None,
                            height=geo_map_height,
                        )
                        if geo_map:
                            st_folium(
                                geo_map,
                                use_container_width=True,
                                height=geo_map_height + 10,
                                returned_objects=["last_clicked"],
                                key="geo_lake_county_folium_map",
                            )
                    else:
                        render_dataset_map(
                            st.session_state[SESSION_KEY_MAP_DATASET_DATA],
                            st.session_state[SESSION_KEY_MAP_AOI_DATA],
                            width=FOLIUM_STATIC_DEFAULT_WIDTH,
                            height=geo_map_height,
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
                        width=FOLIUM_STATIC_DEFAULT_WIDTH,
                        height=FOLIUM_STATIC_DEFAULT_HEIGHT,
                        project_data=st.session_state[SESSION_KEY_MAP_PROJECT_DATA],
                        project_list=st.session_state[SESSION_KEY_MAP_PROJECT_LIST],
                        jurisdiction_boundary=st.session_state[SESSION_KEY_MAP_JURISDICTION_BOUNDARY],
                        county_board_district_boundary=st.session_state.get(SESSION_KEY_MAP_COUNTY_BOARD_DISTRICT_BOUNDARY),
                    )
                else:
                    render_dataset_map(
                        st.session_state[SESSION_KEY_MAP_DATASET_DATA],
                        st.session_state[SESSION_KEY_MAP_AOI_DATA],
                        width=FOLIUM_STATIC_DEFAULT_WIDTH,
                        height=FOLIUM_STATIC_DEFAULT_HEIGHT,
                    )

            if st.session_state.get(SESSION_KEY_DATA_SOURCE) == "geo_lake_county":
                with st.container(key="geo_map_table_debug_wrap"):
                    render_geo_map_bottom_table()
    _map_resize_js = """
        (function() {
            var doc = null;
            try { doc = window.parent.document; } catch (e) { return; }
            function getHost() {
                return doc.querySelector('[data-testid="stVerticalBlock"][class*="st-key-geo_map_iframe_host"]') ||
                    doc.querySelector('[class*="st-key-geo_map_iframe_host"]');
            }
            var PW = window.parent;
            function mapSlotFromHost(host) {
                var inner = host.querySelector(":scope > div");
                var row = inner || host;
                var kids = row.children;
                for (var i = 0; i < kids.length; i++) {
                    var el = kids[i];
                    if (!el.querySelector) continue;
                    var hasEmpty = el.querySelector("[data-testid=\"stEmpty\"]");
                    var hasIframe = el.querySelector("iframe");
                    if (hasEmpty && !hasIframe) continue;
                    if (hasIframe) return el;
                }
                return null;
            }
            function mapIframeInSlot(slot) {
                if (!slot || !slot.querySelectorAll) return null;
                var list = slot.querySelectorAll("iframe");
                if (!list.length) return null;
                var i;
                for (i = 0; i < list.length; i++) {
                    var f = list[i];
                    if (f.classList && f.classList.contains("stCustomComponentV1")) return f;
                }
                for (i = 0; i < list.length; i++) {
                    var g = list[i];
                    var gcls = g.getAttribute("class");
                    if (gcls && gcls.indexOf("stCustomComponent") >= 0) return g;
                }
                var best = null;
                var bestArea = 0;
                for (i = 0; i < list.length; i++) {
                    var h = list[i];
                    var r = h.getBoundingClientRect();
                    var a = Math.max(0, r.width) * Math.max(0, r.height);
                    if (a > bestArea) { bestArea = a; best = h; }
                }
                return best;
            }
            function resizeMapIframe() {
                var host = getHost();
                if (!host) return;
                host.style.removeProperty("height");
                host.style.removeProperty("max-height");
                var slot = mapSlotFromHost(host);
                if (!slot) return;
                var iframe = mapIframeInSlot(slot);
                if (!iframe) return;
                var sr = slot.getBoundingClientRect();
                var ch = Math.floor(slot.clientHeight);
                var avail = ch > 0 ? ch : Math.floor(sr.height);
                if (avail < 120) avail = Math.max(120, Math.floor(sr.height * 0.92));
                if (avail > 60) {
                    iframe.removeAttribute("width");
                    iframe.removeAttribute("height");
                    iframe.style.setProperty("width", "100%", "important");
                    iframe.style.setProperty("height", avail + "px", "important");
                    iframe.style.setProperty("max-height", avail + "px", "important");
                    var wrap = iframe.closest("[data-testid=\"stIFrame\"]");
                    if (wrap) {
                        wrap.style.setProperty("flex", "1 1 0", "important");
                        wrap.style.setProperty("min-height", "0", "important");
                        wrap.style.setProperty("height", avail + "px", "important");
                        wrap.style.setProperty("max-height", avail + "px", "important");
                    } else {
                        var pw = iframe.parentElement;
                        if (pw && slot.contains(pw)) {
                            pw.style.setProperty("min-height", "0", "important");
                            pw.style.setProperty("flex", "1 1 0", "important");
                            pw.style.setProperty("display", "flex", "important");
                            pw.style.setProperty("flex-direction", "column", "important");
                            pw.style.setProperty("height", avail + "px", "important");
                            pw.style.setProperty("max-height", avail + "px", "important");
                            pw.style.setProperty("box-sizing", "border-box", "important");
                        }
                        var cur = pw ? pw.parentElement : null;
                        var up = 0;
                        while (cur && cur !== slot && up < 5) {
                            if (cur.nodeType === 1) {
                                cur.style.setProperty("flex", "1 1 0", "important");
                                cur.style.setProperty("min-height", "0", "important");
                                if (cur.getAttribute && cur.getAttribute("data-testid") === "stVerticalBlock") {
                                    break;
                                }
                            }
                            cur = cur.parentElement;
                            up++;
                        }
                    }
                }
            }
            var parentResizeRaf = null;
            function scheduleResizeMapFromParent() {
                if (parentResizeRaf) return;
                parentResizeRaf = PW.requestAnimationFrame(function() {
                    parentResizeRaf = null;
                    resizeMapIframe();
                });
            }
            PW.addEventListener("resize", scheduleResizeMapFromParent, { passive: true });
            try {
                if (PW.visualViewport) {
                    PW.visualViewport.addEventListener("resize", scheduleResizeMapFromParent, { passive: true });
                }
            } catch (eVV) {}
            var roAttempts = 0;
            function initResizeObserver() {
                var host = getHost();
                if (!host && roAttempts < 90) {
                    roAttempts++;
                    window.parent.requestAnimationFrame(initResizeObserver);
                    return;
                }
                if (!host) return;
                var slot = mapSlotFromHost(host);
                resizeMapIframe();
                window.parent.requestAnimationFrame(function() {
                    window.parent.requestAnimationFrame(resizeMapIframe);
                });
                setTimeout(resizeMapIframe, 300);
                setTimeout(resizeMapIframe, 800);
                setTimeout(resizeMapIframe, 2000);
                if (window.parent.ResizeObserver) {
                    var ro = new window.parent.ResizeObserver(function() {
                        resizeMapIframe();
                    });
                    ro.observe(host);
                    if (slot) ro.observe(slot);
                }
                var mo = new window.parent.MutationObserver(function() {
                    resizeMapIframe();
                });
                mo.observe(host, { childList: true, subtree: true });
                var mapIframe = slot ? mapIframeInSlot(slot) : null;
                if (mapIframe) {
                    mapIframe.addEventListener("load", function() {
                        setTimeout(resizeMapIframe, 50);
                        setTimeout(resizeMapIframe, 400);
                    });
                }
            }
            window.parent.requestAnimationFrame(initResizeObserver);
        })();
    """
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
                var vb = doc.querySelector('[data-testid="stVerticalBlock"][class*="st-key-geo_chat_history"]');
                if (!vb) vb = doc.querySelector('[class*="st-key-geo_chat_history"]');
                if (!vb) return null;
                try {
                    var svb = window.parent.getComputedStyle(vb);
                    if (svb.overflowY === "auto" || svb.overflowY === "scroll") return vb;
                } catch (e0) {}
                var bw = vb.closest('[data-testid="stVerticalBlockBorderWrapper"]');
                if (bw) {
                    try {
                        var st = window.parent.getComputedStyle(bw);
                        if (st.overflowY === "auto" || st.overflowY === "scroll") return bw;
                    } catch (e1) {}
                }
                return findScrollable(vb) || vb;
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
        f"<script>{_map_resize_js}\n{_scroll_chat_to_bottom_js}</script>",
        width=1,
        height=1,
        scrolling=False,
    )

