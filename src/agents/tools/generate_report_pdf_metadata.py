from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

_MAX_TITLE_LEN = 110
_MAX_CONTEXT_LEN = 72


def _sanitize_report_pdf_metadata(
    report_title: str,
    report_context: str,
) -> tuple[str, str] | None:
    t = (report_title or "").strip()
    c = (report_context or "").strip()
    if not t or not c:
        return None
    t = " ".join(t.split())
    c = " ".join(c.split())
    return t[:_MAX_TITLE_LEN], c[:_MAX_CONTEXT_LEN]


@tool("generate_report_pdf_metadata")
async def generate_report_pdf_metadata(
    report_title: str,
    report_context: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Set concise PDF cover metadata for Geo Lake County exports only.

    Call exactly once per user turn when data_source is geo_lake_county, before other
    spatial tools. Output is not shown in chat; it drives PDF banner, hero kicker, and
    main title. Subtitle in PDF remains the user verbatim prompt (handled client-side).

    report_title:
      Short, professional cover title (sentence case). Not the raw user prompt.
      Examples:
      - User: "Tell me about Norway project" -> report_title="Norway Project"
      - User: "show me projects by Nomada" -> report_title="Projects by Nomada"
      - User: "Projects on soil type 530D3" -> report_title="Projects on Soil Type 530D3"

    report_context:
      3–6 words, Title Case, thematic label for executive banner lines (after GEO AI | … ANALYSIS
      and GEO AI - … INTELLIGENCE REPORT). Describe the analysis type, not a project name.
      Examples:
      - User asks about one named project (overview) -> report_context="Project Information"
      - User filters projects by person/org (e.g. by Nomada) -> report_context="Projects by Author"
      - User intersects projects with soils / soil codes -> report_context="Soil Intersection Analysis"
      - User asks projects in jurisdiction/watershed/boundary -> report_context="Location-Filtered Projects"
      - User lists or counts projects by category/status/type -> report_context="Project Portfolio Analysis"
      - User focuses on streams/hydro -> report_context="Hydrospatial Analysis"
      - User focuses on flood zones -> report_context="Flood Hazard Analysis"
      - Generic spatial layer query without projects -> report_context="Layer Intelligence Analysis"
    """
    tid = tool_call_id or ""
    cleaned = _sanitize_report_pdf_metadata(report_title, report_context)
    if not cleaned:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            "Both report_title and report_context must be non-empty. "
                            "Retry with a concise title (professional, not the raw prompt) "
                            "and a short thematic context label for the PDF banner."
                        ),
                        tool_call_id=tid,
                    )
                ],
            },
        )
    title, ctx = cleaned
    return Command(
        update={
            "report_pdf_metadata": {"title": title, "context": ctx},
            "messages": [
                ToolMessage(
                    content="PDF cover metadata recorded.",
                    tool_call_id=tid,
                )
            ],
        },
    )
