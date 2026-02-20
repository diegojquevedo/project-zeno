"""
Build summary and chart from Lake County project/preapp/concern matches.
Used by list_lake_county_projects, list_lake_county_preapps, list_lake_county_concerns,
and search_lake_county_project_descriptions.
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


async def _generate_description_summary(descriptions: list[str], user_query: str, entity_label: str = "project") -> str:
    """Call Gemini to get a 1-2 sentence summary from a list of description texts."""
    combined = "\n---\n".join(descriptions[:10])
    try:
        prompt = f"""Based on these Lake County stormwater {entity_label} descriptions/names/notes, provide a 1-2 sentence contextual summary in the same language as the user query.
Focus on common themes. Be concise.

User query: {user_query}

Texts:
{combined}

Respond with only the summary, no preamble."""
        response = await GEMINI_FLASH.ainvoke(prompt)
        return (response.content or "").strip() if hasattr(response, "content") else str(response).strip()
    except Exception as e:
        logger.warning("LC_DESCRIPTION_SUMMARY_FAILED", entity=entity_label, error=str(e))
        return ""


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
    if descriptions and len(matches) <= 30:
        description_summary = await _generate_description_summary(descriptions, user_query, "project")

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


async def build_preapp_summary_and_chart(
    matches: list,
    user_query: str,
) -> tuple[str, list[dict] | None]:
    """
    Build summary text and chart from preapp matches.
    Uses preapp-specific fields: status, jurisdiction, Subshed, TypeApplication.
    Returns (summary_text, charts_data or None).
    """
    if not matches:
        return "No pre-applications found.", None

    n = len(matches)
    by_status = _count_by_field(matches, "status")
    by_jurisdiction = _count_by_field(matches, "jurisdiction")
    by_subshed = _count_by_field(matches, "Subshed")
    by_type = _count_by_field(matches, "TypeApplication")

    # LLM description summary (only when manageable count and descriptions exist)
    description_summary = ""
    descriptions = _collect_descriptions(matches)
    if descriptions and len(matches) <= 30:
        description_summary = await _generate_description_summary(descriptions, user_query, "pre-application")

    # Build summary text
    lines = [f"# Found {n} pre-application{'s' if n != 1 else ''}"]

    if by_status and len(by_status) > 1:
        parts = [f"{c} {s}" for s, c in sorted(by_status.items(), key=lambda x: -x[1])]
        lines.append(f"\n**By status:** {', '.join(parts)}.")
    elif by_status:
        s, c = next(iter(by_status.items()))
        lines.append(f"\n**Status:** {s} ({c}).")

    if by_type and any(v and v != "(blank)" for v in by_type):
        clean = {k: v for k, v in by_type.items() if k and k != "(blank)"}
        if clean:
            parts = [f"{c} {t}" for t, c in sorted(clean.items(), key=lambda x: -x[1])]
            lines.append(f"**By type:** {', '.join(parts)}.")

    if by_jurisdiction and len(by_jurisdiction) > 1:
        top = sorted(by_jurisdiction.items(), key=lambda x: -x[1])[:8]
        parts = [f"{c} {j}" for j, c in top]
        more = f" and {len(by_jurisdiction) - 8} more" if len(by_jurisdiction) > 8 else ""
        lines.append(f"**By jurisdiction:** {', '.join(parts)}{more}.")

    if by_subshed and len(by_subshed) > 1:
        top = sorted(by_subshed.items(), key=lambda x: -x[1])[:6]
        parts = [f"{c} {s}" for s, c in top]
        lines.append(f"**By sub-watershed:** {', '.join(parts)}.")

    if description_summary:
        lines.append(f"\n**Description summary:** {description_summary}")

    lines.append("\n**Pre-application names:**")
    for i, m in enumerate(matches[:15], 1):
        attrs = m.get("attributes", {})
        name = attrs.get("Name") or attrs.get("Address") or f"PreApp #{attrs.get('preapp_id', '?')}"
        lines.append(f"{i}. {name}")
    if n > 15:
        lines.append(f"... and {n - 15} more.")
    lines.append("\nAll pre-applications are displayed on the map.")

    summary_text = "\n".join(lines)

    # Build charts
    charts = []

    def add_bar(title: str, counts: dict[str, int]) -> None:
        clean = {k: v for k, v in counts.items() if k and k != "(blank)"}
        if len(clean) < 2:
            return
        data = [{"category": k, "count": v} for k, v in sorted(clean.items(), key=lambda x: -x[1])]
        charts.append({
            "id": f"chart_{len(charts)}",
            "title": title,
            "type": "bar",
            "insight": f"Distribution: {', '.join(f'{k} ({v})' for k, v in clean.items())}.",
            "data": data,
            "xAxis": "category",
            "yAxis": "count",
            "colorField": "",
            "stackField": "",
            "groupField": "",
            "seriesFields": [],
        })

    add_bar("Pre-Applications by Status", by_status)
    add_bar("Pre-Applications by Jurisdiction", by_jurisdiction)
    add_bar("Pre-Applications by Sub-Watershed", by_subshed)

    charts_data = charts[:2] if charts else None

    return summary_text, charts_data


def _collect_concern_descriptions(matches: list) -> list[str]:
    """Extract non-empty construction_issue, description, problem from concern matches."""
    texts = []
    for m in matches:
        attrs = m.get("attributes", {})
        for key in ("construction_issue", "description", "problem"):
            v = attrs.get(key)
            if v and str(v).strip():
                texts.append(str(v).strip())
    return texts


async def build_concern_summary_and_chart(
    matches: list,
    user_query: str,
) -> tuple[str, list[dict] | None]:
    """
    Build summary text and charts from concern (CIRS) matches.
    Uses: status_CIRS, problem, jurisdiction, category_report, frequency_problem.
    Returns (summary_text, charts_data or None).
    """
    if not matches:
        return "No concerns found.", None

    n = len(matches)
    by_status = _count_by_field(matches, "status_CIRS")
    by_problem = _count_by_field(matches, "problem")
    by_jurisdiction = _count_by_field(matches, "jurisdiction")
    by_category = _count_by_field(matches, "category_report")
    by_frequency = _count_by_field(matches, "frequency_problem")

    description_summary = ""
    descriptions = _collect_concern_descriptions(matches)
    if descriptions and len(matches) <= 30:
        description_summary = await _generate_description_summary(
            descriptions, user_query, "concern"
        )

    lines = [f"# Found {n} concern{'s' if n != 1 else ''}"]

    if by_status and len(by_status) > 1:
        parts = [f"{c} {s}" for s, c in sorted(by_status.items(), key=lambda x: -x[1])]
        lines.append(f"\n**By status:** {', '.join(parts)}.")
    elif by_status:
        s, c = next(iter(by_status.items()))
        lines.append(f"\n**Status:** {s} ({c}).")

    if by_problem and len(by_problem) > 1:
        parts = [f"{c} {p}" for p, c in sorted(by_problem.items(), key=lambda x: -x[1])]
        lines.append(f"**By problem type:** {', '.join(parts)}.")

    if by_jurisdiction and len(by_jurisdiction) > 1:
        top = sorted(by_jurisdiction.items(), key=lambda x: -x[1])[:8]
        parts = [f"{c} {j}" for j, c in top]
        more = f" and {len(by_jurisdiction) - 8} more" if len(by_jurisdiction) > 8 else ""
        lines.append(f"**By jurisdiction:** {', '.join(parts)}{more}.")

    if by_category and any(k and k != "(blank)" for k in by_category):
        clean = {k: v for k, v in by_category.items() if k and k != "(blank)"}
        if clean:
            parts = [f"{c} {k}" for k, c in sorted(clean.items(), key=lambda x: -x[1])]
            lines.append(f"**By category:** {', '.join(parts)}.")

    if description_summary:
        lines.append(f"\n**Description summary:** {description_summary}")

    lines.append("\n**Concern list:**")
    for i, m in enumerate(matches[:15], 1):
        attrs = m.get("attributes", {})
        cid = attrs.get("concern_id", "?")
        problem = attrs.get("problem") or "—"
        jur = attrs.get("jurisdiction") or "—"
        status = attrs.get("status_CIRS") or "—"
        lines.append(f"{i}. Concern #{cid} — {problem} — {jur} — {status}")
    if n > 15:
        lines.append(f"... and {n - 15} more.")
    lines.append("\nAll concerns are displayed on the map.")

    summary_text = "\n".join(lines)

    charts = []

    def add_bar(title: str, counts: dict[str, int]) -> None:
        clean = {k: v for k, v in counts.items() if k and k != "(blank)"}
        if len(clean) < 2:
            return
        data = [{"category": k, "count": v} for k, v in sorted(clean.items(), key=lambda x: -x[1])]
        charts.append({
            "id": f"chart_{len(charts)}",
            "title": title,
            "type": "bar",
            "insight": f"Distribution: {', '.join(f'{k} ({v})' for k, v in clean.items())}.",
            "data": data,
            "xAxis": "category",
            "yAxis": "count",
            "colorField": "",
            "stackField": "",
            "groupField": "",
            "seriesFields": [],
        })

    add_bar("Concerns by Problem Type", by_problem)
    add_bar("Concerns by Status", by_status)
    add_bar("Concerns by Jurisdiction", by_jurisdiction)

    charts_data = charts[:2] if charts else None

    return summary_text, charts_data
