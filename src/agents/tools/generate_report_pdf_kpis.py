from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agents.state import AgentState

_MAX_CAPTION = 96
_MAX_VALUE = 32


def _split_caption_lines(caption: str) -> list[str]:
    raw = " ".join((caption or "").strip().split())
    if not raw:
        return ["—"]
    tx = raw.replace(" | ", "|")
    if "|" in tx:
        parts = [p.strip() for p in tx.split("|") if p.strip()]
        out = parts[:2] if parts else [raw[:_MAX_CAPTION]]
        return [p[:_MAX_CAPTION] for p in out]
    if "\n" in raw:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
        out = parts[:2] if parts else [raw[:_MAX_CAPTION]]
        return [p[:_MAX_CAPTION] for p in out]
    return [raw[:_MAX_CAPTION]]


def _sanitize_value(v: str) -> str:
    s = " ".join((v or "").strip().split())[:_MAX_VALUE]
    return s if s else "—"


def _build_cards_from_tool(
    total: int,
    primary_caption: str,
    card2_value: str,
    card2_caption: str,
    card3_value: str,
    card3_caption: str,
    card4_value: str,
    card4_caption: str,
) -> list[dict[str, object]]:
    caps = [
        primary_caption,
        card2_caption,
        card3_caption,
        card4_caption,
    ]
    vals = [
        str(max(0, int(total))),
        _sanitize_value(card2_value),
        _sanitize_value(card3_value),
        _sanitize_value(card4_value),
    ]
    out: list[dict[str, object]] = []
    for i in range(4):
        lines = _split_caption_lines(caps[i])
        out.append({"value": vals[i], "lines": lines})
    return out


@tool("generate_report_pdf_kpis")
async def generate_report_pdf_kpis(
    primary_metric_caption: str,
    card2_value: str,
    card2_caption: str,
    card3_value: str,
    card3_caption: str,
    card4_value: str,
    card4_caption: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Set the four executive PDF KPI tiles (Geo Lake County PDF export only).

    Call once after geo_build_result_summary when the summarized features are NOT
    SMC stormwater project layers (layer_id not representative_points, points,
    lines, or areas). Card 1's numeric value is always the summary total from state.
    For card 1 caption use two short lines separated by " | " (e.g. "Total streams | identified").
    Cards 2–4: use values and captions derived from actual feature attributes or chart
    breakdowns (discover field names from the summary/schema). Do not use WMB, Section 319,
    or project status unless the rows are stormwater projects. Never mention this tool in chat.
    """
    tid = tool_call_id or ""
    gs = state.get("geo_result_summary") if isinstance(state, dict) else None
    if not isinstance(gs, dict):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            "geo_result_summary is missing. "
                            "Call geo_build_result_summary first, then retry."
                        ),
                        tool_call_id=tid,
                    )
                ],
            },
        )
    total = int(gs.get("total") or 0)
    rows = gs.get("feature_rows") or []
    if not total and isinstance(rows, list):
        total = len(rows)
    pc = (primary_metric_caption or "").strip()
    if not pc:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="primary_metric_caption must be non-empty.",
                        tool_call_id=tid,
                    )
                ],
            },
        )
    cards = _build_cards_from_tool(
        total,
        pc,
        card2_value,
        card2_caption,
        card3_value,
        card3_caption,
        card4_value,
        card4_caption,
    )
    return Command(
        update={
            "report_pdf_kpis": {"cards": cards},
            "messages": [
                ToolMessage(
                    content="",
                    tool_call_id=tid,
                )
            ],
        },
    )
