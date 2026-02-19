"""
Tool to search Lake County projects by semantic similarity on descriptions.
Filters first (jurisdiction, status, etc.), then ranks by relevance to the query.
"""
from typing import Annotated

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langgraph.types import Command

from src.agent.tools.lake_county_project_summary import build_project_summary_and_chart
from src.api.lake_county_config import PROJECT_CATEGORY_PROJECTS
from src.api.lake_county_service import (
    fetch_lake_county_domains,
    fetch_municipality_boundary,
    query_lake_county_projects,
)
from src.shared.config import SharedSettings
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

TOP_K_SEMANTIC = 15


def _last_user_message(messages: list) -> str:
    """Extract content from last HumanMessage in conversation."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content = getattr(m, "content", None)
            return str(content).strip() if content else ""
    return ""


def _resolve_value(user_value: str, domain_values: list[str]) -> str | None:
    """Case-insensitive match; prefer exact, then startswith, then contains."""
    if not user_value or not domain_values:
        return None
    uv = user_value.strip().lower()
    for d in domain_values:
        if d.lower() == uv:
            return d
    for d in domain_values:
        if d.lower().startswith(uv) or uv in d.lower():
            return d
    return None


def _project_text_for_embedding(attrs: dict) -> str:
    """Build text from Name, Description, Notes for semantic search."""
    parts = []
    name = attrs.get("Name")
    if name and str(name).strip():
        parts.append(str(name).strip())
    desc = attrs.get("Description")
    if desc and str(desc).strip():
        parts.append(str(desc).strip())
    notes = attrs.get("Notes")
    if notes and str(notes).strip():
        parts.append(str(notes).strip())
    return "\n".join(parts) if parts else "Unnamed project"


@tool("search_lake_county_project_descriptions")
async def search_lake_county_project_descriptions(
    semantic_query: str,
    status: str | None = None,
    project_status: str | None = None,
    project_types: list[str] | None = None,
    jurisdiction: str | None = None,
    project_partners: str | None = None,
    subshed: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    Search Lake County projects by semantic similarity on descriptions.
    Use when data_source is Lake County and the user asks about project content/topics, e.g.:
    - "Projects about sewers" -> semantic_query="sewers"
    - "Sewers in Wadsworth" -> semantic_query="sewer drainage", jurisdiction="Wadsworth"
    - "Projects related to drainage in Village of Wadsworth" -> semantic_query="drainage", jurisdiction="Village of Wadsworth"

    First filters by jurisdiction, status, project_status, project_types, project_partners, subshed (if provided).
    Then ranks projects by how well their Description/Name/Notes match the semantic query.
    Returns top 15 most relevant projects.
    """
    semantic_query = (semantic_query or "").strip()
    if not semantic_query:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content="Please provide a semantic query (e.g. 'sewers', 'drainage', 'flood mitigation').",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    domains = await fetch_lake_county_domains()

    resolved_status = None
    if status and str(status).strip():
        resolved = _resolve_value(str(status).strip(), domains.get("status", []))
        resolved_status = resolved if resolved else str(status).strip()

    resolved_project_status = None
    if project_status and str(project_status).strip():
        resolved = _resolve_value(
            str(project_status).strip(), domains.get("ProjectStatus", [])
        )
        resolved_project_status = resolved if resolved else str(project_status).strip()

    jurisdiction_val = jurisdiction.strip() if jurisdiction and str(jurisdiction).strip() else None
    partners_val = project_partners.strip() if project_partners and str(project_partners).strip() else None
    subshed_val = subshed.strip() if subshed and str(subshed).strip() else None

    jurisdiction_boundary = None
    if jurisdiction_val:
        jurisdiction_boundary = await fetch_municipality_boundary(jurisdiction_val)

    project_types_val = [t.strip() for t in project_types if t and str(t).strip()] if project_types else None

    # Default to normal projects (exclude Flood Audit and Study) for semantic search
    result = await query_lake_county_projects(
        status=resolved_status,
        project_status=resolved_project_status,
        project_types=project_types_val,
        jurisdiction=jurisdiction_val,
        project_partners=partners_val,
        subshed=subshed_val,
        project_category=PROJECT_CATEGORY_PROJECTS,
        allow_no_filters=True,
    )

    if not result["found"]:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content="No Lake County projects found matching the filters. Try different criteria.",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    matches = result["matches"]
    limit_exceeded = result.get("limit_exceeded", False)

    docs = []
    for i, m in enumerate(matches):
        attrs = m.get("attributes", {})
        text = _project_text_for_embedding(attrs)
        docs.append(Document(page_content=text, metadata={"idx": i}))

    if not docs:
        return Command(
            update={
                "project_result": None,
                "messages": [
                    ToolMessage(
                        content="No project descriptions available to search.",
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    embeddings = GoogleGenerativeAIEmbeddings(
        model=SharedSettings.dataset_embeddings_model,
        task_type=SharedSettings.dataset_embeddings_task_type,
    )
    store = InMemoryVectorStore(embeddings)
    store.add_documents(docs)

    similar = store.similarity_search_with_score(
        semantic_query,
        k=min(TOP_K_SEMANTIC, len(matches)),
    )

    ranked_matches = []
    for doc, score in similar:
        idx = doc.metadata.get("idx")
        if idx is not None and 0 <= idx < len(matches):
            ranked_matches.append(matches[idx])

    user_query = _last_user_message((state or {}).get("messages", []))
    tool_message, charts_data = await build_project_summary_and_chart(
        ranked_matches, user_query or semantic_query
    )

    if limit_exceeded:
        tool_message += "\n\n**Note:** Initial filter returned 200+ projects. Results are the top matches by description similarity."

    project_result = {
        "list": True,
        "matches": ranked_matches,
        "total_returned": len(ranked_matches),
        "limit_exceeded": limit_exceeded,
    }
    if jurisdiction_boundary and jurisdiction_boundary.get("features"):
        project_result["jurisdiction_boundary"] = jurisdiction_boundary

    update = {
        "project_result": project_result,
        "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)],
    }
    if charts_data:
        update["charts_data"] = charts_data

    return Command(update=update)
