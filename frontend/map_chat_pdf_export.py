import io
import json
import re
from datetime import datetime, timezone
from typing import Any

import vl_convert as vlc
from fpdf import FPDF

from constants import (
    GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER,
    GEO_NARRATIVE_SUGGESTIONS_DELIM,
    MAP_CHAT_PDF_DOCUMENT_TITLE,
    MAP_CHAT_PDF_SECTION_CHARTS,
    MAP_CHAT_PDF_SECTION_FIELDS,
    MAP_CHAT_PDF_SECTION_FOLLOWUP,
    MAP_CHAT_PDF_SECTION_FULL_TABLE,
    MAP_CHAT_PDF_FULL_TABLE_MAX_COLUMNS,
    MAP_CHAT_PDF_FULL_TABLE_MAX_ROWS,
    MAP_CHAT_PDF_SECTION_PROJECT_LIST,
    MAP_CHAT_PDF_SECTION_RECORD_DETAIL,
    MAP_CHAT_PDF_SECTION_RESULTS_DETAIL,
    MAP_CHAT_PDF_SECTION_RICH_CONTEXT,
    MAP_CHAT_PDF_SECTION_SCHEMA,
    MAP_CHAT_PDF_SECTION_SUMMARY,
)

_SKIP = frozenset({"OBJECTID", "GlobalID", "Shape__Area", "Shape__Length"})
_DATE_COLUMNS = frozenset({"StartYear", "EndYear"})
_CELL_PAD_MM = 1.4
_COL_GRAY = (90, 90, 90)
_COL_BLACK = (0, 0, 0)
_COL_BLUE = (30, 80, 160)
_COL_HEADER_BG = (240, 242, 248)
_COL_ROW_ALT = (249, 250, 252)
_COL_DIVIDER = (210, 214, 220)
_COL_ACCENT = (50, 100, 180)


def _truncate_cell_text(
    pdf: FPDF,
    text: str,
    col_w_mm: float,
    *,
    size: int = 8,
    bold: bool = False,
) -> str:
    pdf.set_font("Helvetica", "B" if bold else "", size)
    s = "" if text is None else str(text)
    inner = max(1.0, col_w_mm - _CELL_PAD_MM)
    if pdf.get_string_width(s) <= inner:
        return s
    ell = "..."
    if pdf.get_string_width(ell) > inner:
        return ""
    lo, hi = 0, len(s)
    best = ell
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = s[:mid] + ell
        if pdf.get_string_width(cand) <= inner:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1
    return best


class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)
        self.add_page()
        self.set_margins(12, 12, 12)

    def _set(self, size: int, bold: bool = False, color=_COL_BLACK):
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)

    def h1(self, text: str):
        self._set(18, bold=True, color=_COL_BLUE)
        self.multi_cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h2(self, text: str):
        self.ln(3)
        self._set(13, bold=True, color=_COL_BLACK)
        self.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self._set(0)
        self.set_draw_color(*_COL_DIVIDER)
        x0 = self.get_x()
        self.line(x0, self.get_y(), x0 + self.epw, self.get_y())
        self.ln(2)

    def h3(self, text: str):
        self.ln(2)
        self._set(11, bold=True, color=_COL_ACCENT)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text: str):
        self._set(10, color=_COL_BLACK)
        self.multi_cell(0, 5.5, (text or "").strip(), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def caption(self, text: str):
        self._set(9, color=_COL_GRAY)
        self.multi_cell(0, 5, (text or "").strip(), new_x="LMARGIN", new_y="NEXT")

    def divider(self):
        self.ln(3)
        self.set_draw_color(*_COL_DIVIDER)
        x0 = self.get_x()
        self.line(x0, self.get_y(), x0 + self.epw, self.get_y())
        self.ln(3)

    def full_results_table_landscape(self, rows: list[dict]) -> None:
        max_rows = MAP_CHAT_PDF_FULL_TABLE_MAX_ROWS
        max_cols = MAP_CHAT_PDF_FULL_TABLE_MAX_COLUMNS
        if not rows:
            return
        keys: list[str] = []
        for row in rows:
            for k in row:
                if k not in keys:
                    keys.append(k)
        if not keys:
            return
        keys = keys[:max_cols]
        self.add_page(orientation="L")
        epw = self.epw
        col_w = epw / len(keys)
        row_h_hdr = 6.0
        row_h_data = 5.5

        self.h3(MAP_CHAT_PDF_SECTION_FULL_TABLE)

        def draw_header() -> None:
            self.set_draw_color(*_COL_DIVIDER)
            self.set_fill_color(*_COL_HEADER_BG)
            self._set(8, bold=True, color=_COL_ACCENT)
            for k in keys:
                ht = _truncate_cell_text(self, str(k), col_w, size=8, bold=True)
                self.cell(col_w, row_h_hdr, ht, border=1, fill=True, align="L")
            self.ln()

        draw_header()
        self._set(8, color=_COL_BLACK)
        ymax = self.h - self.b_margin - 8
        for i, row in enumerate(rows[:max_rows]):
            if self.get_y() + row_h_data > ymax:
                self.add_page(orientation="L")
                draw_header()
                self._set(8, color=_COL_BLACK)
            fill = i % 2 == 1
            self.set_fill_color(*(_COL_ROW_ALT if fill else (255, 255, 255)))
            for k in keys:
                val = str(row.get(k) or "")
                tt = _truncate_cell_text(self, val, col_w, size=8, bold=False)
                self.cell(col_w, row_h_data, tt, border=1, fill=fill, align="L")
            self.ln()

        if len(rows) > max_rows:
            self.ln(1)
            self.caption(f"… {len(rows) - max_rows} more rows not shown.")
        self.ln(2)

    def bullet_list(self, items: list[str]):
        self._set(10, color=_COL_BLACK)
        for item in items:
            self.set_x(self.get_x() + 4)
            self.cell(5, 5.5, "-")
            self.multi_cell(self.epw - 9, 5.5, item, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def chart_image(self, png_bytes: bytes, title: str, insight: str = ""):
        if not png_bytes:
            return
        if self.get_y() > 200:
            self.add_page()
        self.h3(title)
        if insight:
            self.caption(insight)
            self.ln(1)
        img = io.BytesIO(png_bytes)
        img_w = min(self.epw, 160)
        self.image(img, x=self.get_x(), y=self.get_y(), w=img_w)
        self.ln(img_w * 0.55 + 4)


def _format_cell(key: str, val) -> str:
    if key not in _DATE_COLUMNS or val is None or str(val) == "None":
        return str(val) if val is not None else ""
    try:
        n = int(val)
        ts = n / 1000 if abs(n) > 1e10 else n
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m/%d/%Y")
    except (ValueError, TypeError, OSError):
        return str(val)


def _split_geo_narrative(full: str) -> tuple[str, str]:
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


def _chart_to_png(chart_data: dict) -> bytes | None:
    data = chart_data.get("data")
    if not isinstance(data, list) or not data:
        return None
    x_field = chart_data.get("xAxis") or "category"
    y_field = chart_data.get("yAxis") or "count"
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": data},
        "mark": {"type": "bar", "color": "#1e50a0"},
        "encoding": {
            "x": {
                "field": x_field,
                "type": "nominal",
                "axis": {"labelAngle": -30},
                "title": x_field.title(),
            },
            "y": {
                "field": y_field,
                "type": "quantitative",
                "title": y_field.title(),
            },
        },
        "width": 380,
        "height": 220,
        "config": {"font": "sans-serif"},
    }
    try:
        return vlc.vegalite_to_png(json.dumps(spec), scale=2)
    except Exception:
        return None


def _strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text.strip()


def _write_geo_summary(pdf: _PDF, geo_summary: dict):
    pdf.divider()
    pdf.h2(MAP_CHAT_PDF_SECTION_RESULTS_DETAIL)

    total = geo_summary.get("total", 0)
    label = geo_summary.get("label_plural", "results")
    filters = geo_summary.get("filters", {}) or {}
    charts_data = geo_summary.get("charts_data") or []
    feature_rows = geo_summary.get("feature_rows", [])

    pdf.body(f"Found {total} {label}")
    if total > 0 and len(feature_rows) < total:
        pdf.caption(
            f"Showing {len(feature_rows)} of {total}; "
            f"the map includes all {total}."
        )

    filter_parts: list[str] = []
    if filters.get("category") and filters["category"] != "projects":
        filter_parts.append(f"Category: {filters['category']}")
    if filters.get("jurisdiction"):
        filter_parts.append(f"In: {filters['jurisdiction']}")
    if filters.get("boundary"):
        filter_parts.append(f"Boundary: {filters['boundary']}")
    if filters.get("status"):
        filter_parts.append(f"Status: {filters['status']}")
    if filter_parts:
        pdf.caption(" · ".join(filter_parts))

    ne = geo_summary.get("narrative_enrichment")
    if ne and str(ne).strip():
        pdf.h3(MAP_CHAT_PDF_SECTION_RICH_CONTEXT)
        pdf.body(_strip_md(str(ne).strip()))

    display_rows = [
        {k: _format_cell(k, v) for k, v in row.items() if k not in _SKIP}
        for row in feature_rows
    ]

    if total == 1 and feature_rows:
        pdf.h3(MAP_CHAT_PDF_SECTION_RECORD_DETAIL)
        row = feature_rows[0]
        dr = {k: _format_cell(k, v) for k, v in row.items() if k not in _SKIP}
        priority = ("Name", "projecttype", "jurisdiction", "watershed", "subwatershed", "project_id")
        for key in priority:
            if dr.get(key) is not None:
                pdf.body(f"{key.replace('_', ' ').title()}: {dr[key]}")
        for k, v in dr.items():
            if k not in priority and v is not None:
                pdf.caption(f"{k}: {v}")

    elif total > 1 and feature_rows:
        pdf.h3(MAP_CHAT_PDF_SECTION_PROJECT_LIST)
        items: list[str] = []
        for row in feature_rows[:20]:
            name = str(row.get("Name") or row.get("project_id") or "Unnamed")
            ptype = row.get("projecttype")
            items.append(f"{name} ({ptype})" if ptype else name)
        if total > 20:
            items.append(f"… and {total - 20} more")
        pdf.bullet_list(items)

    had_landscape_table = False
    if display_rows and total > 0:
        pdf.full_results_table_landscape(display_rows)
        had_landscape_table = True

    if charts_data:
        if had_landscape_table:
            pdf.add_page(orientation="P")
        pdf.h3(MAP_CHAT_PDF_SECTION_CHARTS)
        for ch in charts_data:
            if not isinstance(ch, dict):
                continue
            title = str(ch.get("title") or "Chart")
            insight = _strip_md(str(ch.get("insight") or "").strip())
            png = _chart_to_png(ch)
            if png:
                pdf.chart_image(png, title, insight)
            else:
                pdf.h3(title)
                if insight:
                    pdf.caption(insight)


def _write_schema(pdf: _PDF, snap: dict):
    intro = _strip_md((snap.get("intro") or "").strip())
    fields = _strip_md((snap.get("fields") or "").strip())
    if not intro and not fields:
        return
    pdf.divider()
    pdf.h2(MAP_CHAT_PDF_SECTION_SCHEMA)
    if intro:
        pdf.body(intro)
    if fields:
        pdf.h3(MAP_CHAT_PDF_SECTION_FIELDS)
        pdf.body(fields)


def _write_message(pdf: _PDF, role: str, content: str, geo_fmt: bool):
    label = "You" if role == "user" else "Assistant"
    pdf.h2(label)
    raw = (content or "").strip()
    if not raw:
        return
    if role == "assistant" and geo_fmt:
        if raw == GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER:
            pdf.caption(raw)
            return
        summary_part, sugg_part = _split_geo_narrative(raw)
        if summary_part:
            pdf.h3(MAP_CHAT_PDF_SECTION_SUMMARY)
            pdf.body(_strip_md(summary_part))
        if sugg_part:
            pdf.h3(MAP_CHAT_PDF_SECTION_FOLLOWUP)
            lines = [ln.strip().lstrip("-* \u2022") for ln in sugg_part.splitlines() if ln.strip()]
            pdf.bullet_list(lines)
        if not summary_part and not sugg_part:
            pdf.body(_strip_md(raw))
    else:
        pdf.body(_strip_md(raw))


def build_map_chat_pdf_bytes(
    messages: list[Any],
    *,
    geo_summary: dict | None = None,
    schema_snapshot: dict | None = None,
    data_source: str | None = None,
) -> bytes:
    pdf = _PDF()
    geo_fmt = data_source == "geo_lake_county"

    pdf.h1(MAP_CHAT_PDF_DOCUMENT_TITLE)
    pdf.caption(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    pdf.divider()

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        _write_message(pdf, str(role), str(m.get("content") or ""), geo_fmt)

    if isinstance(schema_snapshot, dict):
        _write_schema(pdf, schema_snapshot)

    if geo_fmt and isinstance(geo_summary, dict):
        _write_geo_summary(pdf, geo_summary)

    return bytes(pdf.output())
