from __future__ import annotations

import re

from langchain_core.messages import HumanMessage

from src.agents.llms import SMALL_MODEL
from src.agents.tools.geo_discover_layer_schema import _fetch_layer_schema
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

_SKIP_FIELDS = frozenset(
    {
        "OBJECTID",
        "GlobalID",
        "SHAPE",
        "Shape",
        "Shape__Area",
        "Shape__Length",
        "_color",
    }
)

_FULL_ROW_SNIPPET_MAX = 25
_SAMPLE_ROW_COUNT = 80
_ENRICHMENT_SKIP_TOTAL_OVER = 2500
_MAX_FIELDS_TO_SCORE = 12
_MAX_SNIPPET_CHARS = 450
_MAX_PROMPT_BODY_CHARS = 14000
_MAX_FREQ_TERMS_PER_FIELD = 16
_FREQ_TERMS_SHOWN = 12
_MIN_TOKEN_LEN = 4

_NARRATIVE_HINT_SUBSTRINGS = (
    "desc",
    "summary",
    "narrative",
    "comment",
    "note",
    "detail",
    "remark",
    "abstract",
    "overview",
    "body",
    "story",
    "rationale",
    "justif",
    "explain",
    "purpose",
    "objective",
    "text",
    "narrat",
    "synopsis",
)

_STRING_LIKE_TYPES = frozenset({"esriFieldTypeString"})


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _hint_score(name: str, alias: str) -> float:
    blob = f"{_norm(name)} {_norm(alias)}"
    score = 0.0
    for hint in _NARRATIVE_HINT_SUBSTRINGS:
        if hint in blob:
            score += 12.0
    return min(score, 36.0)


def _coded_domain_size(domain: dict | None) -> int:
    if not domain or domain.get("type") != "codedValue":
        return 0
    vals = domain.get("codedValues") or []
    return len(vals)


def _schema_field_score(field_def: dict) -> float:
    fn = field_def.get("name") or ""
    if not fn or fn in _SKIP_FIELDS:
        return -999.0
    if fn.upper().startswith("SHAPE"):
        return -999.0
    ftype = field_def.get("type") or ""
    if ftype not in _STRING_LIKE_TYPES:
        return -999.0
    alias = str(field_def.get("alias") or fn)
    score = _hint_score(fn, alias)
    coded_n = _coded_domain_size(field_def.get("domain"))
    if 0 < coded_n <= 48:
        score -= 25.0
    return score


def _avg_non_null_str_len(rows: list[dict], col: str) -> float:
    lens: list[int] = []
    for r in rows:
        v = r.get(col)
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        lens.append(len(s))
    if not lens:
        return 0.0
    return sum(lens) / len(lens)


def _data_score(rows: list[dict], col: str) -> float:
    avg_len = _avg_non_null_str_len(rows, col)
    if avg_len <= 0:
        return -999.0
    return min(avg_len / 8.0, 22.0)


def _unique_ratio(rows: list[dict], col: str) -> float:
    vals = []
    for r in rows:
        v = r.get(col)
        if v is None or not str(v).strip():
            continue
        vals.append(str(v).strip())
    if not vals:
        return 1.0
    return len({*vals}) / len(vals)


def _union_row_keys(feature_rows: list[dict], *, max_rows: int = 2000) -> list[str]:
    keys: set[str] = set()
    n = min(len(feature_rows), max_rows)
    for i in range(n):
        keys.update(k for k in feature_rows[i].keys() if k not in _SKIP_FIELDS)
    return list(keys)


def _pick_narrative_columns(
    feature_rows: list[dict],
    schema_data: dict | None,
) -> list[str]:
    if not feature_rows:
        return []
    row_keys = _union_row_keys(feature_rows)
    if not row_keys:
        return []

    scored: list[tuple[float, str]] = []

    field_defs: dict[str, dict] = {}
    if schema_data and schema_data.get("fields"):
        for fd in schema_data["fields"]:
            n = fd.get("name")
            if isinstance(n, str) and n:
                field_defs[n] = fd

    for col in row_keys:
        ds = _data_score(feature_rows, col)
        if ds < -100:
            continue
        ur = _unique_ratio(feature_rows, col)
        if ur < 0.12 and _avg_non_null_str_len(feature_rows, col) < 28:
            ds -= 10.0

        ss = 0.0
        fd = field_defs.get(col)
        if fd:
            ss = _schema_field_score(fd)
            if ss < -100:
                continue
        else:
            ss = _hint_score(col, col) * 0.35

        total = ss + ds
        if total > 0:
            scored.append((total, col))

    scored.sort(key=lambda x: -x[0])
    out = [c for _, c in scored[:_MAX_FIELDS_TO_SCORE]]
    if len(out) < 2 and schema_data:
        for col in row_keys:
            if col in out:
                continue
            fd = field_defs.get(col)
            if not fd:
                continue
            if _schema_field_score(fd) < -50:
                continue
            ds = _data_score(feature_rows, col)
            if ds > 3 and col not in out:
                out.append(col)
            if len(out) >= 2:
                break

    if not out:
        rest = sorted(
            row_keys,
            key=lambda c: -_avg_non_null_str_len(feature_rows, c),
        )
        for c in rest[:3]:
            if _avg_non_null_str_len(feature_rows, c) >= 18:
                out.append(c)

    return out[:3]


def _clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _rows_for_snippets(all_rows: list[dict], total: int) -> tuple[list[dict], bool]:
    if total > _ENRICHMENT_SKIP_TOTAL_OVER:
        return [], False
    if total <= _FULL_ROW_SNIPPET_MAX:
        return all_rows, False
    n = min(_SAMPLE_ROW_COUNT, total)
    if n >= total:
        return all_rows, False
    step = (total - 1) / max(n - 1, 1)
    picked: list[dict] = []
    seen_i: set[int] = set()
    for k in range(n):
        i = min(int(round(k * step)), total - 1)
        if i in seen_i:
            continue
        seen_i.add(i)
        picked.append(all_rows[i])
    return picked, True


def _build_snippet_block(
    feature_rows: list[dict],
    columns: list[str],
    *,
    anonymize_headers: bool,
) -> str:
    lines: list[str] = []
    for j, col in enumerate(columns, start=1):
        hdr = f"Excerpt group {j}" if anonymize_headers else f"Field `{col}`"
        lines.append(f"{hdr}:")
        for i, row in enumerate(feature_rows, start=1):
            v = row.get(col)
            if v is None or not str(v).strip():
                continue
            lines.append(f"  - item {i}: {_clip(str(v), _MAX_SNIPPET_CHARS)}")
        lines.append("")
    return "\n".join(lines).strip()


def _token_freq_for_column(rows: list[dict], col: str) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    pat = re.compile(rf"[a-z][a-z0-9']{{{_MIN_TOKEN_LEN - 1},}}", re.I)
    for r in rows:
        v = r.get(col)
        if v is None:
            continue
        s = str(v).strip().lower()
        if not s:
            continue
        for m in pat.finditer(s):
            w = m.group(0)
            if len(w) < _MIN_TOKEN_LEN:
                continue
            counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return ranked[:_MAX_FREQ_TERMS_PER_FIELD]


def _full_corpus_stats_block(all_rows: list[dict], columns: list[str], total: int) -> str:
    lines = [
        f"Total records in this result: {total} (every record was scanned for the signals below).",
    ]
    for idx, col in enumerate(columns, start=1):
        non_null = 0
        lens: list[int] = []
        for r in all_rows:
            v = r.get(col)
            if v is None or not str(v).strip():
                continue
            non_null += 1
            lens.append(len(str(v).strip()))
        pct = (100.0 * non_null / total) if total else 0.0
        avg_len = sum(lens) / len(lens) if lens else 0.0
        mx = max(lens) if lens else 0
        spread = "sparse across records" if pct < 25 else "uncommon" if pct < 55 else "common" if pct < 85 else "very common"
        depth = "mostly brief" if avg_len < 80 else "mixed length" if avg_len < 200 else "often detailed"
        lines.append(
            f"Text bundle {idx} (internal): text present for ~{pct:.0f}% of records ({spread}); "
            f"typical depth {depth} (mean ~{avg_len:.0f} chars when present, longest ~{mx})."
        )
        terms = _token_freq_for_column(all_rows, col)
        if terms:
            shown = ", ".join(f"{w} ({c})" for w, c in terms[:_FREQ_TERMS_SHOWN])
            lines.append(f"  Recurring words across all text in this bundle: {shown}")
    return "\n".join(lines)


async def compute_narrative_enrichment(
    feature_rows: list[dict],
    layer_url: str | None,
    *,
    total: int,
    result_label: str,
) -> str | None:
    if total <= 0 or not feature_rows:
        return None

    schema_data: dict | None = None
    if layer_url:
        try:
            schema_data = await _fetch_layer_schema(layer_url)
        except Exception as e:
            logger.warning("narrative_enrichment_schema_failed", error=str(e))

    columns = _pick_narrative_columns(feature_rows, schema_data)
    if not columns:
        logger.warning(
            "narrative_enrichment_no_columns",
            total=total,
            feature_row_count=len(feature_rows),
        )
        return None

    snippet_rows, from_sample = _rows_for_snippets(feature_rows, total)
    if not snippet_rows:
        return None

    stats_block = ""
    if total > _FULL_ROW_SNIPPET_MAX:
        stats_block = _full_corpus_stats_block(feature_rows, columns, total)

    body = _build_snippet_block(snippet_rows, columns, anonymize_headers=True)
    if (not body or len(body) < 12) and from_sample:
        alt_n = min(40, total)
        snippet_rows = feature_rows[:alt_n]
        body = _build_snippet_block(snippet_rows, columns, anonymize_headers=True)
    if not body or len(body) < 12:
        return None

    if stats_block:
        body = (
            f"=== INTERNAL — evidence over all {total} records (do not quote numbers or column names to the reader) ===\n"
            f"{stats_block}\n\n"
            f"=== Example excerpts from evenly spaced records ===\n{body}"
        )

    if len(body) > _MAX_PROMPT_BODY_CHARS:
        body = body[:_MAX_PROMPT_BODY_CHARS] + "\n…(truncated)"

    if stats_block:
        prompt = (
            "You write a short plain-language brief for non-technical readers (e.g. residents, board members, "
            "program managers). They care what these records are broadly about — problems, goals, activities, "
            "themes — not how the data is stored.\n\n"
            f"Topic label (context only): {result_label!r}. About {total} records were analyzed.\n\n"
            "You receive two kinds of input: (1) INTERNAL numeric and word-frequency signals computed over "
            "every record for a few auto-picked text columns (chosen from layer metadata and text length, "
            "not a hand-maintained field list), and (2) example excerpts from evenly spaced records.\n\n"
            "Write 3–6 sentences in clear English. Focus on substance: what most or many of these items "
            "relate to, recurring problems or purposes, typical work or outcomes, and any clear patterns in "
            "wording. Use everyday language (e.g. “many projects”, “commonly”, “often”, “broadly”).\n\n"
            "STRICTLY FORBIDDEN in your output: percentages, fractions of rows, “non-empty”, character or "
            "word counts, averages, min/max length, database or GIS jargon (fields, attributes, layers, "
            "schema, tokens), quoting internal column names, or repeating the internal statistics verbatim. "
            "Do not sound like a data dictionary or QA report.\n\n"
            "Ground themes in the internal signals and excerpts, but translate them into a readable story. "
            "Do not invent specific project names, addresses, or numbers not supported by the excerpts. "
            "If the texts are mostly empty or generic, say in one simple sentence that there is little "
            "descriptive detail to summarize.\n\n"
            f"---\n{body}\n---"
        )
    else:
        prompt = (
            "You write a short plain-language brief for non-technical readers about a small set of map records.\n\n"
            f"Topic label (context only): {result_label!r}. Count: {total}.\n"
            "Below are text values from a few auto-selected columns (from layer metadata and text length, "
            "not a fixed field list).\n\n"
            "Write 1–4 sentences in clear English: what these items are about, common themes or problems, "
            "typical activities. No engineering vocabulary, no schema talk, no percentages unless they appear "
            "literally in the quoted text. Stay grounded in the snippets; do not invent facts. If there is "
            "no usable text, say so in one sentence.\n\n"
            f"---\n{body}\n---"
        )

    try:
        msg = await SMALL_MODEL.ainvoke([HumanMessage(content=prompt)])
        text = (getattr(msg, "content", None) or "").strip()
        if isinstance(text, list):
            text = "".join(str(p) for p in text).strip()
        if not text or len(text) < 8:
            return None
        return text
    except Exception as e:
        logger.warning("narrative_enrichment_llm_failed", error=str(e))
        return None
