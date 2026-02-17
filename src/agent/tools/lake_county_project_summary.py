"""
Build summary and chart from Lake County project matches.
Used by list_lake_county_projects and search_lake_county_project_descriptions.
"""
from collections import Counter

from src.agent.llms import GEMINI_FLASH
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _collect_descriptions(matches: list) -> list[str]:
    """Extract non-empty Description, Name, Notes from matches."""
    texts = []
    for m in matches:
        attrs = m.get("attributes", {})
        for key in ("Description", "Name", "Notes"):
            v = attrs.get(key)
            if v and str(v).strip():
                texts.append(str(v).strip())
    return texts


def _count_by_field(matches: list, field: str) -> dict[str, int]:
    """Count projects by attribute field value."""
    c: Counter[str] = Counter()
    for m in matches:
        attrs = m.get("attributes", {})
        v = attrs.get(field)
        label = str(v).strip() if v is not None and str(v).strip() else "(blank)"
        c[label] += 1
    return dict(c)


def _collect_partners(matches: list) -> set[str]:
    """Collect unique project partners from ProjectPartners (comma-separated)."""
    partners = set()
    for m in matches:
        attrs = m.get("attributes", {})
        v = attrs.get("ProjectPartners")
        if v and str(v).strip():
            for p in str(v).split(","):
                p = p.strip()
                if p:
                    partners.add(p)
    return partners


def _build_summary_text(
    matches: list,
    by_projecttype: dict[str, int],
    by_status: dict[str, int],
    by_project_status: dict[str, int],
    partners: set[str],
    description_summary: str,
    user_query: str,
) -> str:
    """Build the mini-report text."""
    n = len(matches)
    lines = [f"# Found {n} project{'s' if n != 1 else ''}"]

    if by_projecttype:
        parts = [f"{c} {t}" for t, c in sorted(by_projecttype.items(), key=lambda x: -x[1])]
        lines.append(f"\n**By project type:** {', '.join(parts)}.")
    if by_status:
        parts = [f"{c} {t}" for t, c in sorted(by_status.items(), key=lambda x: -x[1])]
        lines.append(f"**By status:** {', '.join(parts)}.")
    if by_project_status:
        parts = [f"{c} {t}" for t, c in sorted(by_project_status.items(), key=lambda x: -x[1])]
        lines.append(f"**By project status:** {', '.join(parts)}.")
    if partners:
        sorted_partners = sorted(partners)[:15]
        more = f" and {len(partners) - 15} more" if len(partners) > 15 else ""
        lines.append(f"**Project partners:** {', '.join(sorted_partners)}{more}.")

    if description_summary:
        lines.append(f"\n**Description summary:** {description_summary}")

    lines.append("\n**Project names:**")
    for i, m in enumerate(matches[:15], 1):
        name = m.get("attributes", {}).get("Name", f"Project {i}")
        lines.append(f"{i}. {name}")
    if len(matches) > 15:
        lines.append(f"... and {len(matches) - 15} more.")
    lines.append("\nAll projects are shown on the map.")
    return "\n".join(lines)


def _build_chart_data(
    matches: list,
    by_projecttype: dict[str, int],
    by_status: dict[str, int],
    by_project_status: dict[str, int],
) -> list[dict] | None:
    """
    Build chart data for dimensions with variation. Prefer status, then ProjectStatus, then projecttype.
    Returns charts_data list or None if no meaningful chart.
    """
    charts = []

    def add_bar_chart(title: str, counts: dict[str, int]) -> None:
        if len(counts) < 2:
            return
        data = [{"category": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        charts.append({
            "id": f"chart_{len(charts)}",
            "title": title,
            "type": "bar",
            "insight": f"Distribution: {', '.join(f'{k} ({v})' for k, v in counts.items())}.",
            "data": data,
            "xAxis": "category",
            "yAxis": "count",
            "colorField": "",
            "stackField": "",
            "groupField": "",
            "seriesFields": [],
        })

    add_bar_chart("Projects by Status", by_status)
    add_bar_chart("Projects by Project Status", by_project_status)
    add_bar_chart("Projects by Type", by_projecttype)

    return charts[:2] if charts else None


async def build_project_summary_and_chart(
    matches: list,
    user_query: str,
) -> tuple[str, list[dict] | None]:
    """
    Build summary text and optional chart from project matches.
    Returns (summary_text, charts_data or None).
    """
    if not matches:
        return "No projects found.", None

    by_projecttype = _count_by_field(matches, "projecttype")
    by_status = _count_by_field(matches, "status")
    by_project_status = _count_by_field(matches, "ProjectStatus")
    partners = _collect_partners(matches)

    description_summary = ""
    descriptions = _collect_descriptions(matches)
    if descriptions:
        combined = "\n---\n".join(descriptions[:20])  # Limit for token budget
        if len(descriptions) > 20:
            combined += "\n[... more descriptions omitted]"
        try:
            prompt = f"""Based on these Lake County stormwater project descriptions/names/notes, provide a 2-3 sentence contextual summary in the same language as the user query.
Focus on: what topics do they cover (e.g. sewers, drainage, viaducts, flood areas, water quality)? Any common themes?

User query: {user_query}

Project texts:
{combined}

Respond with only the summary, no preamble."""
            response = await GEMINI_FLASH.ainvoke(prompt)
            description_summary = (response.content or "").strip() if hasattr(response, "content") else str(response).strip()
        except Exception as e:
            logger.warning("LC_DESCRIPTION_SUMMARY_FAILED", error=str(e))

    summary_text = _build_summary_text(
        matches,
        by_projecttype,
        by_status,
        by_project_status,
        partners,
        description_summary,
        user_query,
    )

    charts_data = _build_chart_data(matches, by_projecttype, by_status, by_project_status)

    return summary_text, charts_data
