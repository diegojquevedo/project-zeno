import io
import json
import re
from datetime import datetime, timezone
from typing import Any

import vl_convert as vlc
from fpdf import FPDF
from geo_feature_display import (
    geo_feature_row_display_id,
    geo_feature_row_display_label,
)

from constants import (
    CHART_NOMINAL_COLOR_SCHEME,
    COLOR,
    GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER,
    GEO_NARRATIVE_SUGGESTIONS_DELIM,
    GEO_RESULT_SUMMARY_UI_OMIT_RESULTS_DETAIL_KEY,
    MAP_CHAT_PDF,
)

_SKIP = frozenset({"OBJECTID", "GlobalID", "Shape__Area", "Shape__Length"})
_DATE_COLUMNS = frozenset({"StartYear", "EndYear"})
_CELL_PAD_MM = 1.4

_SCHEMA_FIELD_RE = re.compile(
    r"\*\*(?P<name>[^*]+)\*\*\s*\((?P<ftype>[^)]+)\)\s*:\s*(?P<alias>.*?)(?=\s+-\s+\*\*|\s+(?=\*\*[^*]+\*\*\s*\()|\Z)",
    re.DOTALL,
)

def _spaced_caps_line(title: str) -> str:
    parts = [p for p in title.upper().replace("&", "AND").split() if p]
    return "   ".join(" ".join(list(w)) for w in parts)


def _truncate_cell_text(
    pdf: FPDF,
    text: str,
    col_w_mm: float,
    *,
    size: int = 8,
    bold: bool = False,
) -> str:
    pdf.set_font("Helvetica", "B" if bold else "", size)
    s = _pdf_text("" if text is None else str(text))
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


def _format_cell(key: str, val) -> str:
    if key not in _DATE_COLUMNS or val is None or str(val) == "None":
        return str(val) if val is not None else ""
    try:
        n = int(val)
        ts = n / 1000 if abs(n) > 1e10 else n
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m/%d/%Y")
    except (ValueError, TypeError, OSError):
        return str(val)


def _strip_internal_instructions(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    kept: list[str] = []
    for p in re.split(r"\n\s*\n+", t):
        pl = p.strip()
        if re.match(r"(?is)^If the user wants features within this project", pl):
            continue
        if re.match(r"(?is)^If the user only wanted project info", pl):
            continue
        if re.search(r"(?i)geo_spatial_intersection", pl) and "call" in pl.lower():
            continue
        kept.append(pl)
    return "\n\n".join(kept).strip()


def _split_project_attributes_from_text(text: str) -> tuple[str, list[tuple[str, str]], str]:
    t = (text or "").strip()
    if not t:
        return "", [], ""
    m = re.search(
        r"(?is)(?:^|\n)\s*\*{0,2}\s*Project attributes\s*:?\s*\*{0,2}\s*\n",
        t,
    )
    if not m:
        return t, [], ""
    intro = t[: m.start()].strip()
    rest = t[m.end() :]
    rows: list[tuple[str, str]] = []
    lines = rest.splitlines()
    tail_start = len(lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            if rows:
                tail_start = i
                break
            continue
        bullet = re.match(r"^[-*•]\s*(.+)$", s)
        if not bullet:
            if rows:
                tail_start = i
                break
            continue
        inner = bullet.group(1).strip()
        if ":" not in inner:
            if rows:
                tail_start = i
                break
            continue
        k, _, v = inner.partition(":")
        ks, vs = k.strip(), v.strip()
        if ks:
            rows.append((ks, _format_cell(ks, vs)))
        else:
            if rows:
                tail_start = i
                break
    tail = "\n".join(lines[tail_start:]).strip()
    tail = _strip_internal_instructions(tail)
    return intro, rows, tail


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


def _strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text.strip()


def _pdf_text(s: str) -> str:
    t = "" if s is None else str(s)
    t = (
        t.replace("\u2014", " - ")
        .replace("\u2013", "-")
        .replace("\u2026", "...")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
        .replace("\u2022", "-")
        .replace("\u00b7", "-")
        .replace("\u2219", "-")
        .replace("\u25cf", "-")
        .replace("\u25aa", "-")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )
    return t.encode("latin-1", errors="replace").decode("latin-1")


def _landscape_cell_style(col_idx: int, key: str) -> tuple[tuple[int, int, int], bool]:
    if col_idx == 0:
        return COLOR.NAVY, True
    kl = str(key).lower()
    if "description" in kl:
        return COLOR.GRAY, False
    if any(s in kl for s in ("type", "cost", "dollar", "estimated")):
        return COLOR.LIGHT_BLUE, False
    return COLOR.BLACK, False


def _normalize_inventory_field_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (k or "").lower())


def _inventory_column_header_label(key: str) -> str:
    nk = _normalize_inventory_field_key(key)
    mapped = MAP_CHAT_PDF.INVENTORY.HEADER_LABELS.get(nk)
    if mapped is not None:
        return mapped
    s = str(key).strip()
    if not s:
        return ""
    if "_" in s or "-" in s or " " in s:
        return " ".join(p.upper() for p in re.split(r"[_\s-]+", s) if p)
    if re.search(r"[a-z]", s) and re.search(r"[A-Z]", s):
        spaced = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", s)
        return " ".join(p.upper() for p in spaced.split() if p)
    return s.upper()


def _inventory_column_weight(key: str) -> float:
    nk = _normalize_inventory_field_key(key)
    if nk in MAP_CHAT_PDF.INVENTORY.WIDE_COLUMN_KEYS:
        return MAP_CHAT_PDF.INVENTORY.COL_WEIGHT_WIDE
    return MAP_CHAT_PDF.INVENTORY.COL_WEIGHT_DEFAULT


def _word_wrap_lines_sized(
    pdf: FPDF,
    text: str,
    max_w: float,
    size: int,
    bold: bool,
) -> list[str]:
    pdf.set_font("Helvetica", "B" if bold else "", size)
    words = text.replace("\n", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    line = words[0]
    for w in words[1:]:
        test = f"{line} {w}"
        if pdf.get_string_width(test) <= max_w:
            line = test
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines


def _draw_hero_text_block(
    pdf: FPDF,
    main_title: str,
    session_utc: str,
    *,
    hero_copy: Any = None,
) -> None:
    c = hero_copy if hero_copy is not None else MAP_CHAT_PDF.EXEC.COPY
    epw = pdf.epw
    pdf.set_font("Helvetica", "", MAP_CHAT_PDF.HERO.KICKER.PT)
    pdf.set_text_color(*COLOR.WHITE)
    pdf.multi_cell(
        epw,
        MAP_CHAT_PDF.HERO.KICKER.LINE_H_MM,
        _pdf_text(_spaced_caps_line(c.HERO_KICKER)),
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", "", MAP_CHAT_PDF.HERO.KICKER.PT)
    pdf.set_text_color(*COLOR.WHITE)
    pdf.multi_cell(
        epw,
        MAP_CHAT_PDF.HERO.KICKER.LINE_H_MM,
        _pdf_text(_spaced_caps_line(c.HERO_SUBKICKER)),
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(MAP_CHAT_PDF.HERO.LN_AFTER.KICKERS_MM)
    pdf.set_font("Helvetica", "B", MAP_CHAT_PDF.HERO.TITLE.PT)
    pdf.set_text_color(*COLOR.WHITE)
    title_txt = _pdf_text((main_title or "").strip())
    pdf.multi_cell(
        epw,
        MAP_CHAT_PDF.HERO.TITLE.CELL_H_MM,
        title_txt,
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(MAP_CHAT_PDF.HERO.LN_AFTER.TITLE_MM)
    pdf.set_font("Helvetica", "", MAP_CHAT_PDF.HERO.SUBTITLE.PT)
    pdf.set_text_color(*COLOR.HERO_SUBTITLE)
    pdf.cell(epw, MAP_CHAT_PDF.HERO.SUBTITLE.CELL_H_MM, c.HERO_SUBTITLE, align="C")
    pdf.ln(MAP_CHAT_PDF.HERO.LN_AFTER.SUBTITLE_MM)
    pdf.set_font("Helvetica", "", MAP_CHAT_PDF.HERO.META.PT)
    pdf.set_text_color(*COLOR.LIGHT_BLUE)
    meta = _pdf_text(
        f"Lake County, Illinois · Session: {session_utc} · {MAP_CHAT_PDF.EXEC.PREPARED_BY}"
    )
    pdf.multi_cell(
        epw,
        MAP_CHAT_PDF.HERO.META.LINE_H_MM,
        meta,
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _measure_hero_content_height_mm(
    main_title: str,
    session_utc: str,
    *,
    hero_copy: Any = None,
) -> float:
    p = FPDF()
    p.set_margins(12, 14, 12)
    p.add_page()
    y0 = p.get_y()
    _draw_hero_text_block(p, main_title, session_utc, hero_copy=hero_copy)
    return p.get_y() - y0


def _kpi_is_numeric_only(val: str) -> bool:
    t = (val or "").strip()
    return bool(t) and t.isdigit()


def _kpi_value_block_height_mm(pdf: FPDF, inner: float, val: str) -> float:
    if _kpi_is_numeric_only(val):
        return MAP_CHAT_PDF.KPI.VALUE_NUM_LINE_H_MM
    nv = len(
        _word_wrap_lines_sized(
            pdf,
            val,
            inner,
            MAP_CHAT_PDF.KPI.VALUE_PT,
            True,
        )
    )
    return nv * MAP_CHAT_PDF.KPI.VALUE_LINE_H_MM


def _kpi_label_height_mm(pdf: FPDF, inner: float, lab_txt: str) -> float:
    n = 0
    for para in lab_txt.split("\n"):
        p = para.strip()
        if not p:
            continue
        n += len(
            _word_wrap_lines_sized(
                pdf,
                p,
                inner,
                MAP_CHAT_PDF.KPI.LABEL_PT,
                False,
            )
        )
    return n * MAP_CHAT_PDF.KPI.LABEL_LINE_H_MM


def _last_assistant_narrative(messages: list[Any]) -> tuple[str, str]:
    summary = ""
    sugg = ""
    for m in reversed(messages):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        raw = (m.get("content") or "").strip()
        if raw == GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER:
            continue
        summary, sugg = _split_geo_narrative(raw)
        if summary or sugg:
            return _strip_md(summary), _strip_md(sugg)
        return _strip_md(raw), ""
    return "", ""


def _hero_main_title(geo_summary: dict) -> str:
    filters = geo_summary.get("filters") or {}
    b = filters.get("boundary") or ""
    j = filters.get("jurisdiction") or ""
    if b:
        t = str(b).split("\u2013")[0].split("-")[0].strip()
        return t[:80] if t else "Drainage district"
    if j:
        return str(j)[:80]
    return "Lake County projects"


def _kpi_counts(feature_rows: list[dict], total: int) -> tuple[int, int, int, str]:
    wmb = 0
    s319 = 0
    for r in feature_rows:
        pt = str(r.get("projecttype") or "").upper()
        if "WMB" in pt or pt == "WMB":
            wmb += 1
        if "319" in pt:
            s319 += 1
    statuses = [str(r.get("AgreementStatus") or r.get("ProjectStatus") or r.get("status") or "") for r in feature_rows]
    st_clean = [s for s in statuses if s.strip()]
    if st_clean and len(set(st_clean)) == 1:
        st_label = st_clean[0][:40]
    elif st_clean:
        st_label = "Mixed"
    else:
        st_label = "Completed"
    return total, wmb, s319, st_label


def _sum_investment(feature_rows: list[dict]) -> float | None:
    s = 0.0
    n = 0
    for r in feature_rows:
        for k in ("finalcost", "FinalCost", "estimatedcost", "EstimatedCost", "dollarsrequested"):
            v = r.get(k)
            if v is None:
                continue
            try:
                s += float(v)
                n += 1
                break
            except (TypeError, ValueError):
                pass
    return s if n else None


def _schema_key_values(geo_summary: dict, schema_snapshot: dict | None) -> list[tuple[str, str]]:
    filters = geo_summary.get("filters") or {}
    rows = [
        ("Layer", "Drainage Districts"),
        ("Geometry type", "esriGeometryPolygon"),
    ]
    if filters.get("jurisdiction"):
        rows.append(("Jurisdiction", str(filters["jurisdiction"])))
    name_f = filters.get("boundary") or filters.get("jurisdiction") or ""
    if name_f:
        rows.append(("Filter field", f'NAME = "{name_f.split(chr(8211))[0].strip()}"' if name_f else ""))
    br = filters.get("boundary")
    if br:
        rows.append(("Boundary result", str(br)))
    return [(a, b) for a, b in rows if b]


def _parse_schema_field_entries(raw: str) -> list[tuple[str, str, str]]:
    t = (raw or "").replace("\n", " ")
    rows: list[tuple[str, str, str]] = []
    for m in _SCHEMA_FIELD_RE.finditer(t):
        name = (m.group("name") or "").strip()
        ftype = (m.group("ftype") or "").strip()
        alias = (m.group("alias") or "").strip()
        if name:
            rows.append((name, ftype, alias))
    return rows


def _fallback_schema_dot_list(raw: str) -> list[tuple[str, str, str]]:
    line = (raw or "").replace("\n", " ").strip()
    parts = [p.strip() for p in re.split(r"[·•]", line) if p.strip()]
    out: list[tuple[str, str, str]] = []
    for p in parts[:50]:
        clean = _strip_md(p).strip()
        if clean:
            out.append((clean, "", clean))
    return out


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    return (
        int.from_bytes(png_bytes[16:20], "big"),
        int.from_bytes(png_bytes[20:24], "big"),
    )


def _schema_field_rows(schema_snapshot: dict | None) -> list[tuple[str, str, str]]:
    raw = ""
    if isinstance(schema_snapshot, dict):
        raw = (schema_snapshot.get("fields") or "").strip()
    if not raw:
        raw = "OBJECTID · CODE · NAME · Shape_Leng · projecttype · jurisdiction"
    parsed = _parse_schema_field_entries(raw)
    if parsed:
        return parsed[:60]
    return _fallback_schema_dot_list(raw)


def _chart_to_png(chart_data: dict) -> bytes | None:
    data = chart_data.get("data")
    if not isinstance(data, list) or not data:
        return None
    x_field = chart_data.get("xAxis") or "category"
    y_field = chart_data.get("yAxis") or "count"
    color_field_raw = chart_data.get("colorField")
    color_field = (
        str(color_field_raw).strip()
        if isinstance(color_field_raw, str) and color_field_raw.strip()
        else ""
    )
    xs_title = str(x_field).replace("_", " ").title()
    ys_title = str(y_field).replace("_", " ").title()
    distinct_x: set[str] = set()
    for row in data:
        if isinstance(row, dict) and x_field in row:
            distinct_x.add(str(row.get(x_field)))
    multi_cat = len(distinct_x) > 1
    mark: dict = {"type": "bar"}
    encoding: dict[str, Any] = {
        "x": {
            "field": x_field,
            "type": "nominal",
            "scale": {"paddingInner": 0.12, "paddingOuter": 0.08},
            "axis": {
                "labelAngle": -45,
                "labelAlign": "right",
                "labelBaseline": "bottom",
                "labelLimit": 0,
                "labelOverlap": True,
                "titlePadding": 18,
                "labelPadding": 6,
                "labelOffset": 4,
                "tickBand": "center",
                "tickSize": 5,
                "zindex": 1,
            },
            "title": xs_title,
        },
        "y": {
            "field": y_field,
            "type": "quantitative",
            "title": ys_title,
        },
    }
    if color_field:
        encoding["color"] = {
            "field": color_field,
            "type": "nominal",
            "scale": {"scheme": CHART_NOMINAL_COLOR_SCHEME},
            "legend": {"orient": "top-right", "offset": 4},
        }
    elif multi_cat:
        encoding["color"] = {
            "field": x_field,
            "type": "nominal",
            "scale": {"scheme": CHART_NOMINAL_COLOR_SCHEME},
            "legend": None,
        }
    else:
        mark["color"] = "#1e50a0"
    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": data},
        "mark": mark,
        "encoding": encoding,
        "width": 400,
        "height": 300,
        "autosize": {"type": "fit", "contains": "padding"},
        "config": {
            "font": "sans-serif",
            "axisX": {"labelFontSize": 9, "titleFontSize": 11},
            "axisY": {"labelFontSize": 9, "titleFontSize": 11},
        },
    }
    try:
        return vlc.vegalite_to_png(json.dumps(spec), scale=2)
    except Exception:
        return None


class _PDF(FPDF):
    def __init__(
        self,
        *,
        executive: bool = False,
        banner_lead: str | None = None,
        banner_tail: str | None = None,
    ):
        super().__init__()
        self.executive = executive
        self.banner_lead = banner_lead
        self.banner_tail = banner_tail
        self.alias_nb_pages()
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(12, 14, 12)
        self.footer_left = "Lake County, Illinois"
        self.session_line = ""
        self.add_page()

    def header(self) -> None:
        if not self.executive:
            return
        self.set_font("Helvetica", "", 8)
        lead_src = (
            self.banner_lead
            if self.banner_lead is not None
            else MAP_CHAT_PDF.EXEC.BANNER.LEAD
        )
        tail_src = (
            self.banner_tail
            if self.banner_tail is not None
            else MAP_CHAT_PDF.EXEC.BANNER.TAIL
        )
        lead = _pdf_text(_spaced_caps_line(lead_src))
        tail = _pdf_text(_spaced_caps_line(tail_src))
        gap = "   "
        wl = self.get_string_width(lead)
        wg = self.get_string_width(gap)
        wt = self.get_string_width(tail)
        total_w = wl + wg + wt
        x0 = self.l_margin + (self.epw - total_w) / 2
        y = self.get_y()
        self.set_xy(x0, y)
        self.set_text_color(*COLOR.BLACK)
        self.cell(wl, 5, lead, ln=0)
        self.set_text_color(*COLOR.ACCENT)
        self.cell(wg + wt, 5, gap + tail, ln=1)
        self.set_draw_color(*COLOR.ACCENT)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-16)
        self.set_draw_color(*COLOR.DIVIDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(self.epw / 2, 4, self.footer_left, align="L")
        self.cell(self.epw / 2, 4, f"Page {self.page_no()}/{{nb}}", align="R")

    def _set(self, size: int, bold: bool = False, color=COLOR.BLACK):
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)

    def section_spaced(self, title: str) -> None:
        self.ln(4)
        self._set(9, bold=True, color=COLOR.ACCENT)
        self.multi_cell(0, 4.5, _pdf_text(_spaced_caps_line(title)), new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        self.set_draw_color(*COLOR.ACCENT)
        self.set_line_width(0.3)
        x0 = self.get_x()
        self.line(x0, self.get_y(), x0 + self.epw, self.get_y())
        self.set_line_width(0.2)
        self.ln(3)

    def hero_navy(
        self,
        main_title: str,
        session_utc: str,
        *,
        hero_copy: Any = None,
    ) -> None:
        content_h = _measure_hero_content_height_mm(
            main_title,
            session_utc,
            hero_copy=hero_copy,
        )
        pad_v = MAP_CHAT_PDF.HERO.PAD_V_MM
        h_box = content_h + 2 * pad_v
        y0 = self.get_y()
        self.set_fill_color(*COLOR.NAVY)
        self.rect(self.l_margin, y0, self.epw, h_box, "F")
        self.set_xy(self.l_margin, y0 + pad_v)
        _draw_hero_text_block(self, main_title, session_utc, hero_copy=hero_copy)
        self.set_xy(self.l_margin, y0 + h_box + 4)

    def kpi_four(self, total: int, wmb: int, s319: int, status_lbl: str) -> None:
        self.ln(2)
        gap = 2.0
        w = (self.epw - 3 * gap) / 4
        inner = w - 4
        specs = [
            (str(total), ["Total projects", "identified"]),
            (str(wmb), ["WMB projects"]),
            (str(s319), ["Section 319", "projects"]),
            (_pdf_text(status_lbl.strip() or "Status"), ["All projects", "status"]),
        ]
        x0 = self.get_x()
        y0 = self.get_y()
        max_val_block = 0.0
        max_lab_h = 0.0
        for val, lines in specs:
            max_val_block = max(
                max_val_block,
                _kpi_value_block_height_mm(self, inner, val),
            )
            lab_txt = "\n".join(ln.upper() for ln in lines)
            max_lab_h = max(max_lab_h, _kpi_label_height_mm(self, inner, lab_txt))
        h_val_zone = max_val_block
        y_label_row = (
            y0
            + MAP_CHAT_PDF.KPI.TOP_PAD_MM
            + h_val_zone
            + MAP_CHAT_PDF.KPI.VALUE_LABEL_GAP_MM
        )
        h_box = (y_label_row - y0) + max_lab_h + MAP_CHAT_PDF.KPI.BOTTOM_PAD_MM
        for i in range(4):
            x = x0 + i * (w + gap)
            self.set_xy(x, y0)
            self.set_fill_color(*COLOR.KPI_BG)
            self.rect(x, y0, w, h_box, "F")
        for i, (val, lines) in enumerate(specs):
            x = x0 + i * (w + gap)
            vx = x + 2
            block_h = _kpi_value_block_height_mm(self, inner, val)
            y_val = (
                y0
                + MAP_CHAT_PDF.KPI.TOP_PAD_MM
                + max(0.0, (h_val_zone - block_h) / 2)
            )
            self.set_xy(vx, y_val)
            self.set_text_color(*COLOR.NAVY)
            if _kpi_is_numeric_only(val):
                self.set_font("Helvetica", "B", MAP_CHAT_PDF.KPI.VALUE_NUM_PT)
                self.multi_cell(
                    inner,
                    MAP_CHAT_PDF.KPI.VALUE_NUM_LINE_H_MM,
                    _pdf_text(val),
                    align="C",
                )
            else:
                self.set_font("Helvetica", "B", MAP_CHAT_PDF.KPI.VALUE_PT)
                self.multi_cell(
                    inner,
                    MAP_CHAT_PDF.KPI.VALUE_LINE_H_MM,
                    _pdf_text(val),
                    align="C",
                )
        for i, (_, lines) in enumerate(specs):
            x = x0 + i * (w + gap)
            vx = x + 2
            lab_txt = "\n".join(ln.upper() for ln in lines)
            self.set_xy(vx, y_label_row)
            self.set_font("Helvetica", "", MAP_CHAT_PDF.KPI.LABEL_PT)
            self.set_text_color(*COLOR.LIGHT_BLUE)
            self.multi_cell(
                inner,
                MAP_CHAT_PDF.KPI.LABEL_LINE_H_MM,
                _pdf_text(lab_txt),
                align="C",
            )
        self.set_xy(x0, y0 + h_box + 4)

    def kv_pairs(self, pairs: list[tuple[str, str]]) -> None:
        if not pairs:
            return
        label_w = 52.0
        val_w = self.epw - label_w
        row_h = 8.0
        for lab, val in pairs:
            self.set_fill_color(230, 236, 244)
            self.set_text_color(*COLOR.NAVY)
            self.set_font("Helvetica", "B", 9)
            self.cell(label_w, row_h, f"  {_pdf_text(lab)}", border=0, fill=True, align="L")
            self.set_fill_color(*COLOR.WHITE)
            v = _pdf_text(str(val)[:500])
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*COLOR.BLACK)
            self.cell(val_w, row_h, f"  {v[:220]}", border=0, fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def schema_fields_table(self, rows: list[tuple[str, str, str]]) -> None:
        if not rows:
            return
        w1 = 44.0
        w2 = 48.0
        w3 = max(40.0, self.epw - w1 - w2)
        hdr_h = 6.5
        row_h = 6.0
        self.set_font("Helvetica", "B", 7)
        self.set_fill_color(*COLOR.HEADER_BG)
        self.set_text_color(*COLOR.NAVY)
        self.cell(w1, hdr_h, f"  {MAP_CHAT_PDF.SCHEMA_TABLE.COL_FIELD.upper()}", border=0, fill=True, align="L")
        self.cell(w2, hdr_h, f"  {MAP_CHAT_PDF.SCHEMA_TABLE.COL_TYPE.upper()}", border=0, fill=True, align="L")
        self.cell(w3, hdr_h, f"  {MAP_CHAT_PDF.SCHEMA_TABLE.COL_ALIAS.upper()}", border=0, fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
        for i, (name, ftype, alias) in enumerate(rows):
            fill = i % 2 == 1
            self.set_fill_color(*(COLOR.ROW_ALT if fill else COLOR.WHITE))
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*COLOR.NAVY)
            t1 = _truncate_cell_text(self, name, w1, size=8, bold=True)
            self.cell(w1, row_h, f"  {t1}", border=0, fill=True, align="L")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*COLOR.BLACK)
            t2 = _truncate_cell_text(self, ftype if ftype.strip() else "-", w2, size=8, bold=False)
            self.cell(w2, row_h, f"  {t2}", border=0, fill=True, align="L")
            t3 = _truncate_cell_text(self, alias if alias.strip() else "-", w3, size=8, bold=False)
            self.cell(w3, row_h, f"  {t3}", border=0, fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body(self, text: str) -> None:
        self._set(10, color=COLOR.BLACK)
        self.multi_cell(0, 5.5, _pdf_text((text or "").strip()), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def caption(self, text: str) -> None:
        self._set(9, color=COLOR.GRAY)
        self.multi_cell(0, 5, _pdf_text((text or "").strip()), new_x="LMARGIN", new_y="NEXT")

    def portfolio_cards(
        self,
        wmb: int,
        s319: int,
        total: int,
        invest: float | None,
    ) -> None:
        self.section_spaced(MAP_CHAT_PDF.SECTION.PORTFOLIO_SUMMARY)
        gap = 2.0
        w = (self.epw - 2 * gap) / 3
        h_box = MAP_CHAT_PDF.PORTFOLIO.CARD_HEIGHT_MM
        x0 = self.get_x()
        y0 = self.get_y()
        pct_wmb = round(100 * wmb / total, 0) if total else 0
        pct_319 = round(100 * s319 / total, 0) if total else 0
        inv_line = f"${invest:,.0f}" if invest is not None else "N/A"
        blocks: list[tuple[tuple[int, int, int], str, str]] = [
            (
                COLOR.CARD_BLUE,
                "By project type",
                f"WMB - {wmb} projects ({pct_wmb}%)\n"
                f"Section 319 - {s319} projects ({pct_319}%)",
            ),
            (
                COLOR.CARD_BLUE,
                "By project status",
                f"Completed - {total} of {total} (100%)\nAll agreements: Approved",
            ),
            (
                COLOR.CARD_NAVY,
                "Total investment",
                "",
            ),
        ]
        for i, (fill, title, body) in enumerate(blocks):
            x = x0 + i * (w + gap)
            self.set_fill_color(*fill)
            self.rect(x, y0, w, h_box, "F")
            is_navy = fill == COLOR.CARD_NAVY
            ins = MAP_CHAT_PDF.PORTFOLIO.CARD_INSET_MM
            inner_w = w - 2 * ins
            y_card = y0 + ins
            if is_navy:
                self.set_xy(x + ins, y_card)
                self.set_font("Helvetica", "B", MAP_CHAT_PDF.PORTFOLIO.NAVY.TITLE_PT)
                self.set_text_color(*COLOR.WHITE)
                self.multi_cell(
                    inner_w,
                    MAP_CHAT_PDF.PORTFOLIO.NAVY.TITLE_LINE_H_MM,
                    _pdf_text(_spaced_caps_line("TOTAL INVESTMENT")),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                self.ln(MAP_CHAT_PDF.PORTFOLIO.NAVY.GAP_AFTER_TITLE_MM)
                self.set_x(x + ins)
                self.set_font("Helvetica", "B", MAP_CHAT_PDF.PORTFOLIO.NAVY.VALUE_PT)
                self.set_text_color(*COLOR.WHITE)
                self.cell(
                    inner_w,
                    MAP_CHAT_PDF.PORTFOLIO.NAVY.VALUE_LINE_H_MM,
                    inv_line,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                self.ln(MAP_CHAT_PDF.PORTFOLIO.NAVY.GAP_AFTER_VALUE_MM)
                self.set_x(x + ins)
                self.set_font("Helvetica", "", MAP_CHAT_PDF.PORTFOLIO.NAVY.SUBTITLE_PT)
                self.set_text_color(*COLOR.WHITE)
                self.multi_cell(
                    inner_w,
                    MAP_CHAT_PDF.PORTFOLIO.NAVY.SUBTITLE_LINE_H_MM,
                    _pdf_text(f"Combined final cost across all {total} projects"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            else:
                self.set_xy(x + ins, y_card)
                self.set_font("Helvetica", "B", MAP_CHAT_PDF.PORTFOLIO.LIGHT.TITLE_PT)
                self.set_text_color(*COLOR.NAVY)
                self.cell(
                    inner_w,
                    MAP_CHAT_PDF.PORTFOLIO.LIGHT.TITLE_CELL_H_MM,
                    title.upper(),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                self.ln(MAP_CHAT_PDF.PORTFOLIO.LIGHT.GAP_AFTER_TITLE_MM)
                self.set_x(x + ins)
                self.set_font("Helvetica", "", MAP_CHAT_PDF.PORTFOLIO.LIGHT.BODY_PT)
                self.set_text_color(*COLOR.BLACK)
                self.multi_cell(
                    inner_w,
                    MAP_CHAT_PDF.PORTFOLIO.LIGHT.BODY_LINE_H_MM,
                    _pdf_text(body),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
        self.set_xy(x0, y0 + h_box + 6)

    def numbered_zebra_lines(self, lines: list[str], *, max_rows: int = 12) -> None:
        if not lines:
            return
        num_w = MAP_CHAT_PDF.FOLLOWUP.NUM_COL_W_MM
        pad = MAP_CHAT_PDF.FOLLOWUP.CELL_PAD_MM
        line_h = MAP_CHAT_PDF.FOLLOWUP.LINE_H_MM
        text_w = self.epw - num_w
        text_inner = max(20.0, text_w - 2 * pad)
        ymax = self.h - self.b_margin - 6
        capped = lines[:max_rows]
        for idx, ln in enumerate(capped):
            i = idx + 1
            clean = _pdf_text(_strip_md(ln))
            self.set_font("Helvetica", "", 9)
            nlines = max(
                1,
                len(_word_wrap_lines_sized(self, clean, text_inner, 9, False)),
            )
            row_h = max(8.0, nlines * line_h + 2 * pad)
            y0 = self.get_y()
            x0 = self.l_margin
            if y0 + row_h > ymax:
                self.add_page()
                y0 = self.get_y()
                x0 = self.l_margin
            fill_right = COLOR.WHITE if idx % 2 == 0 else COLOR.TABLE_ZEBRA
            self.set_fill_color(*COLOR.BLUE)
            self.rect(x0, y0, num_w, row_h, "F")
            self.set_fill_color(*fill_right)
            self.rect(x0 + num_w, y0, text_w, row_h, "F")
            self.set_draw_color(218, 222, 228)
            self.line(x0, y0 + row_h, x0 + self.epw, y0 + row_h)
            num_line_h = 5.0
            y_num = y0 + max(pad, (row_h - num_line_h) / 2)
            self.set_xy(x0, y_num)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*COLOR.WHITE)
            self.cell(num_w, num_line_h, f"{i:02d}", align="C")
            self.set_xy(x0 + num_w + pad, y0 + pad)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*COLOR.BLACK)
            self.multi_cell(text_inner, line_h, clean, border=0, fill=False)
            self.set_xy(self.l_margin, y0 + row_h)
        self.ln(2)
        if len(lines) > max_rows:
            self.caption(f"... {len(lines) - max_rows} more rows not shown.")

    def numbered_followups(
        self,
        lines: list[str],
        *,
        section_title: str | None = None,
    ) -> None:
        if not lines:
            return
        title = (
            section_title
            if section_title is not None
            else MAP_CHAT_PDF.SECTION.SUGGESTED_FOLLOWUPS
        )
        self.section_spaced(title)
        self.numbered_zebra_lines(lines, max_rows=12)

    def section_subtitle_accent(self, text: str) -> None:
        self.ln(1)
        self._set(10, bold=True, color=COLOR.ACCENT)
        self.multi_cell(0, 5.5, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def individual_project_results_attributes(
        self,
        attr_lines: list[str],
    ) -> None:
        if not attr_lines:
            return
        self.section_spaced(MAP_CHAT_PDF.SECTION.INDIVIDUAL_PROJECT_RESULTS_DETAIL)
        self.section_subtitle_accent(MAP_CHAT_PDF.SECTION.PROJECT_ATTRIBUTES)
        self.numbered_zebra_lines(attr_lines, max_rows=80)

    def field_value_zebra_rows(self, rows: list[tuple[str, str]]) -> None:
        if not rows:
            return
        self.section_spaced(MAP_CHAT_PDF.SECTION.PROJECT_ATTRIBUTES)
        key_w = MAP_CHAT_PDF.PROJECT_ATTR.KEY_COL_W_MM
        val_w = self.epw - key_w
        pad = MAP_CHAT_PDF.FOLLOWUP.CELL_PAD_MM
        line_h = MAP_CHAT_PDF.FOLLOWUP.LINE_H_MM
        key_inner = max(12.0, key_w - 2 * pad)
        val_inner = max(20.0, val_w - 2 * pad)
        ymax = self.h - self.b_margin - 6
        for idx, (key, val) in enumerate(rows[:80]):
            k_txt = _pdf_text(_strip_md(str(key)))
            v_txt = _pdf_text(_strip_md(str(val)))
            self.set_font("Helvetica", "B", 8)
            nk = max(
                1,
                len(_word_wrap_lines_sized(self, k_txt, key_inner, 8, True)),
            )
            self.set_font("Helvetica", "", 9)
            nv = max(
                1,
                len(_word_wrap_lines_sized(self, v_txt, val_inner, 9, False)),
            )
            nlines = max(nk, nv)
            row_h = max(8.0, nlines * line_h + 2 * pad)
            y0 = self.get_y()
            x0 = self.l_margin
            if y0 + row_h > ymax:
                self.add_page()
                y0 = self.get_y()
                x0 = self.l_margin
            fill_right = COLOR.WHITE if idx % 2 == 0 else COLOR.TABLE_ZEBRA
            self.set_fill_color(*COLOR.BLUE)
            self.rect(x0, y0, key_w, row_h, "F")
            self.set_fill_color(*fill_right)
            self.rect(x0 + key_w, y0, val_w, row_h, "F")
            self.set_draw_color(218, 222, 228)
            self.line(x0, y0 + row_h, x0 + self.epw, y0 + row_h)
            y_text = y0 + pad
            self.set_xy(x0 + pad, y_text)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*COLOR.WHITE)
            self.multi_cell(
                key_inner,
                line_h,
                k_txt,
                align="L",
                border=0,
                fill=False,
            )
            self.set_xy(x0 + key_w + pad, y_text)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*COLOR.BLACK)
            self.multi_cell(
                val_inner,
                line_h,
                v_txt,
                align="L",
                border=0,
                fill=False,
            )
            self.set_xy(self.l_margin, y0 + row_h)
        self.ln(2)
        if len(rows) > 80:
            self.caption(f"... {len(rows) - 80} more attributes not shown.")

    def disclaimer(self) -> None:
        self.ln(4)
        self.set_draw_color(*COLOR.DIVIDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(110, 110, 110)
        self.multi_cell(0, 4, MAP_CHAT_PDF.EXEC.DISCLAIMER, align="C", new_x="LMARGIN", new_y="NEXT")

    def h1(self, text: str) -> None:
        self._set(18, bold=True, color=COLOR.BLUE)
        self.multi_cell(0, 9, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h2(self, text: str) -> None:
        self.ln(3)
        self._set(13, bold=True, color=COLOR.BLACK)
        self.multi_cell(0, 7, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*COLOR.DIVIDER)
        x0 = self.get_x()
        self.line(x0, self.get_y(), x0 + self.epw, self.get_y())
        self.ln(2)

    def h3(self, text: str) -> None:
        self.ln(2)
        self._set(11, bold=True, color=COLOR.ACCENT)
        self.multi_cell(0, 6, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def divider(self) -> None:
        self.ln(3)
        self.set_draw_color(*COLOR.DIVIDER)
        x0 = self.get_x()
        self.line(x0, self.get_y(), x0 + self.epw, self.get_y())
        self.ln(3)

    def full_results_table_landscape(
        self,
        rows: list[dict],
        *,
        inventory_section: bool = False,
        inventory_intro: str | None = None,
    ) -> None:
        max_rows = MAP_CHAT_PDF.FULL_TABLE.MAX_ROWS
        max_cols = MAP_CHAT_PDF.FULL_TABLE.MAX_COLUMNS
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
        if inventory_section:
            self.section_spaced(MAP_CHAT_PDF.SECTION.PROJECT_INVENTORY)
            if inventory_intro:
                self.caption(inventory_intro)
            self.ln(2)

        epw = self.epw
        pad = 1.2
        wsum = sum(_inventory_column_weight(k) for k in keys)
        col_widths = [epw * (_inventory_column_weight(k) / wsum) for k in keys]
        inner_ws = [max(8.0, col_widths[j] - 2 * pad) for j in range(len(keys))]
        line_h = 3.8
        hdr_font = MAP_CHAT_PDF.INVENTORY.HDR_FONT_PT
        hdr_line_h = MAP_CHAT_PDF.INVENTORY.HDR_LINE_H_MM
        hdr_pad = MAP_CHAT_PDF.INVENTORY.HDR_PAD_MM
        ymax = self.h - self.b_margin - 8

        def draw_column_headers() -> None:
            y_top = self.get_y()
            self.set_font("Helvetica", "B", hdr_font)
            nlines_hdr: list[int] = []
            for j, k in enumerate(keys):
                lab = _pdf_text(_inventory_column_header_label(k))
                iw = max(1.0, col_widths[j] - 2 * hdr_pad)
                nlines_hdr.append(
                    max(1, len(_word_wrap_lines_sized(self, lab, iw, hdr_font, True))),
                )
            max_hdr_lines = max(nlines_hdr)
            hdr_row_h = max_hdr_lines * hdr_line_h + 2 * hdr_pad
            x = self.l_margin
            for _j in range(len(keys)):
                wcol = col_widths[_j]
                self.set_fill_color(*COLOR.NAVY)
                self.rect(x, y_top, wcol, hdr_row_h, "F")
                x += wcol
            x = self.l_margin
            for j, k in enumerate(keys):
                wcol = col_widths[j]
                lab = _pdf_text(_inventory_column_header_label(k))
                self.set_xy(x + hdr_pad, y_top + hdr_pad)
                self.set_font("Helvetica", "B", hdr_font)
                self.set_text_color(*COLOR.WHITE)
                self.multi_cell(
                    wcol - 2 * hdr_pad,
                    hdr_line_h,
                    lab,
                    align="L",
                    border=0,
                    fill=False,
                )
                x += wcol
            self.set_xy(self.l_margin, y_top + hdr_row_h)

        draw_column_headers()
        self.ln(1)

        for i, row in enumerate(rows[:max_rows]):
            texts: list[str] = []
            line_counts: list[int] = []
            for j, k in enumerate(keys):
                txt = _pdf_text(str(row.get(k) or ""))
                color, bold = _landscape_cell_style(j, k)
                self.set_font("Helvetica", "B" if bold else "", 8)
                nlines = max(
                    1,
                    len(_word_wrap_lines_sized(self, txt, inner_ws[j], 8, bold)),
                )
                line_counts.append(nlines)
                texts.append(txt)
            row_h = max(line_counts) * line_h + 2 * pad
            y0 = self.get_y()
            if y0 + row_h > ymax:
                self.add_page(orientation="L")
                draw_column_headers()
                self.ln(1)
                y0 = self.get_y()
                line_counts = []
                for j, k in enumerate(keys):
                    txt = _pdf_text(str(row.get(k) or ""))
                    color, bold = _landscape_cell_style(j, k)
                    self.set_font("Helvetica", "B" if bold else "", 8)
                    nlines = max(
                        1,
                        len(_word_wrap_lines_sized(self, txt, inner_ws[j], 8, bold)),
                    )
                    line_counts.append(nlines)
                row_h = max(line_counts) * line_h + 2 * pad

            fill_bg = COLOR.TABLE_ZEBRA if i % 2 == 1 else COLOR.WHITE
            self.set_fill_color(*fill_bg)
            self.rect(self.l_margin, y0, epw, row_h, "F")

            x = self.l_margin
            for j, k in enumerate(keys):
                color, bold = _landscape_cell_style(j, k)
                txt = texts[j]
                cw = col_widths[j]
                self.set_xy(x + pad, y0 + pad)
                self.set_font("Helvetica", "B" if bold else "", 8)
                self.set_text_color(*color)
                self.multi_cell(
                    cw - 2 * pad,
                    line_h,
                    txt,
                    align="L",
                    border=0,
                    fill=False,
                )
                x += cw
            self.set_xy(self.l_margin, y0 + row_h)

        if len(rows) > max_rows:
            self.ln(1)
            self.caption(f"... {len(rows) - max_rows} more rows not shown.")
        self.ln(2)

    def bullet_list(self, items: list[str]) -> None:
        self._set(10, color=COLOR.BLACK)
        for item in items:
            self.set_x(self.get_x() + 4)
            self.cell(5, 5.5, "-")
            self.multi_cell(self.epw - 9, 5.5, _pdf_text(item), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def chart_image(
        self,
        png_bytes: bytes,
        title: str,
        insight: str = "",
        *,
        charts_section: bool = False,
    ) -> None:
        if not png_bytes:
            return
        pw, ph = _png_dimensions(png_bytes)
        img_w = min(self.epw, MAP_CHAT_PDF.CHART.IMAGE_MAX_W_MM)
        img_h = img_w * (ph / pw) if pw > 0 and ph > 0 else img_w * 0.62
        gap_after = MAP_CHAT_PDF.CHART.IMAGE_BOTTOM_GAP_MM
        title_reserve = 30.0 if insight else 20.0
        section_reserve = (
            MAP_CHAT_PDF.CHART.SECTION_RESERVE_MM if charts_section else 0.0
        )
        bottom_limit = self.h - self.b_margin
        if self.get_y() + section_reserve + title_reserve + img_h + gap_after > bottom_limit:
            self.add_page()
        if charts_section:
            self.section_spaced(MAP_CHAT_PDF.SECTION.CHARTS)
        self.ln(2)
        self._set(11, bold=True, color=COLOR.ACCENT)
        self.multi_cell(
            self.epw,
            6,
            _pdf_text(title),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(1)
        if insight:
            self._set(9, bold=False, color=COLOR.GRAY)
            self.multi_cell(
                self.epw,
                5,
                _pdf_text(insight),
                align="C",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            self.ln(1)
        img = io.BytesIO(png_bytes)
        x_img = self.l_margin + (self.epw - img_w) / 2
        self.image(img, x=x_img, y=self.get_y(), w=img_w, h=img_h)
        self.ln(img_h + gap_after)
        self.set_x(self.l_margin)


def _build_executive_geo_pdf(
    messages: list[Any],
    geo_summary: dict,
    schema_snapshot: dict | None,
) -> bytes:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf = _PDF(executive=True)
    pdf.footer_left = _pdf_text(f"{_hero_main_title(geo_summary)} · Lake County")
    pdf.session_line = stamp

    feature_rows = geo_summary.get("feature_rows") or []
    total = int(geo_summary.get("total", 0) or len(feature_rows))
    filters = geo_summary.get("filters") or {}
    charts_data = geo_summary.get("charts_data") or []

    pdf.hero_navy(_hero_main_title(geo_summary), stamp)
    tw, wmb, s319, st_lbl = _kpi_counts(feature_rows, total)
    pdf.kpi_four(tw, wmb, s319, st_lbl)

    exec_sum, _sugg_from_msg = _last_assistant_narrative(messages)
    if not exec_sum:
        exec_sum = _strip_md(str(geo_summary.get("narrative_enrichment") or ""))[:4000]
    if exec_sum:
        pdf.section_spaced(MAP_CHAT_PDF.SECTION.EXECUTIVE_SUMMARY)
        pdf.body(exec_sum)

    pdf.section_spaced(MAP_CHAT_PDF.SECTION.DATA_SOURCE_SCHEMA)
    pdf.kv_pairs(_schema_key_values(geo_summary, schema_snapshot))

    ks_rows = _schema_field_rows(schema_snapshot)
    pdf._set(9, bold=True, color=COLOR.NAVY)
    pdf.multi_cell(0, 5, MAP_CHAT_PDF.EXEC.KEY_SCHEMA_LABEL, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.schema_fields_table(ks_rows)

    boundary = str(filters.get("boundary") or "the selected boundary")
    display_rows = [
        {k: _format_cell(k, v) for k, v in row.items() if k not in _SKIP}
        for row in feature_rows
    ]
    if display_rows:
        inv_intro = (
            f"The following {total} project(s) were identified within {boundary}. "
            f"{MAP_CHAT_PDF.PROJECT_TABLE.INTRO_WRAP_HINT}"
        )
        pdf.full_results_table_landscape(
            display_rows,
            inventory_section=True,
            inventory_intro=inv_intro,
        )

    pdf.add_page(orientation="P")
    invest = _sum_investment(feature_rows)
    pdf.portfolio_cards(wmb, s319, total, invest)

    ne = geo_summary.get("narrative_enrichment")
    thematic = _strip_md(str(ne or "").strip())
    if thematic and exec_sum and thematic not in exec_sum:
        pdf.section_spaced(MAP_CHAT_PDF.SECTION.THEMATIC_CONTEXT)
        pdf.body(thematic)
    elif thematic and not exec_sum:
        pdf.section_spaced(MAP_CHAT_PDF.SECTION.THEMATIC_CONTEXT)
        pdf.body(thematic)

    if charts_data:
        charts_header_done = False
        for ch in charts_data:
            if not isinstance(ch, dict):
                continue
            title = str(ch.get("title") or "Chart")
            insight = _strip_md(str(ch.get("insight") or "").strip())
            png = _chart_to_png(ch)
            if png:
                pdf.chart_image(
                    png,
                    title,
                    insight,
                    charts_section=not charts_header_done,
                )
                charts_header_done = True
            else:
                if not charts_header_done:
                    pdf.section_spaced(MAP_CHAT_PDF.SECTION.CHARTS)
                    charts_header_done = True
                pdf.h3(title)
                if insight:
                    pdf.caption(insight)

    fu_lines: list[str] = []
    _, sugg = _last_assistant_narrative(messages)
    if sugg:
        fu_lines = [ln.strip().lstrip("-* ") for ln in sugg.splitlines() if ln.strip()]
    if fu_lines:
        pdf.numbered_followups(fu_lines)

    pdf.disclaimer()
    return bytes(pdf.output())


def _write_geo_summary_legacy(pdf: _PDF, geo_summary: dict):
    total = geo_summary.get("total", 0)
    label = geo_summary.get("label_plural", "results")
    filters = geo_summary.get("filters", {}) or {}
    charts_data = geo_summary.get("charts_data") or []
    feature_rows = geo_summary.get("feature_rows", [])
    _omit_detail = (
        geo_summary.get(GEO_RESULT_SUMMARY_UI_OMIT_RESULTS_DETAIL_KEY) is True
    )

    display_rows = [
        {k: _format_cell(k, v) for k, v in row.items() if k not in _SKIP}
        for row in feature_rows
    ]

    if not _omit_detail:
        pdf.divider()
        pdf.h2(MAP_CHAT_PDF.SECTION.RESULTS_DETAIL)

        pdf.body(f"Found {total} {label}")
        if total > 0 and len(feature_rows) < total:
            pdf.caption(f"Showing {len(feature_rows)} of {total}; the map includes all {total}.")

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
            pdf.h3(MAP_CHAT_PDF.SECTION.RICH_CONTEXT)
            pdf.body(_strip_md(str(ne).strip()))

        if total == 1 and feature_rows:
            pdf.h3(MAP_CHAT_PDF.SECTION.RECORD_DETAIL)
            row = feature_rows[0]
            dr = {k: _format_cell(k, v) for k, v in row.items() if k not in _SKIP}
            priority = (
                "Name",
                "projecttype",
                "jurisdiction",
                "watershed",
                "subwatershed",
                "project_id",
                "SOILCODE",
                "SOIL_CODE",
                "MUKEY",
                "musym",
                "MUSYM",
                "MAPUNIT_NAME",
                "Mapunit_Name",
            )
            for key in priority:
                if dr.get(key) is not None:
                    pdf.body(f"{key.replace('_', ' ').title()}: {dr[key]}")
            for k, v in dr.items():
                if k not in priority and v is not None:
                    pdf.caption(f"{k}: {v}")

        elif total > 1 and feature_rows:
            pdf.h3(str(label).strip().title())
            items: list[str] = []
            for row in feature_rows[:20]:
                disp = geo_feature_row_display_label(row)
                if disp == "\u2014":
                    rid = geo_feature_row_display_id(row)
                    disp = str(rid) if rid != "\u2014" else "Unnamed"
                ptype = row.get("projecttype")
                items.append(f"{disp} ({ptype})" if ptype else disp)
            if total > 20:
                items.append(f"... and {total - 20} more")
            pdf.bullet_list(items)

    had_landscape_table = False
    if display_rows and total > 0:
        pdf.h3(MAP_CHAT_PDF.SECTION.FULL_TABLE)
        pdf.full_results_table_landscape(display_rows)
        had_landscape_table = True

    if charts_data:
        if had_landscape_table:
            pdf.add_page(orientation="P")
        charts_header_done = False
        for ch in charts_data:
            if not isinstance(ch, dict):
                continue
            title = str(ch.get("title") or "Chart")
            insight = _strip_md(str(ch.get("insight") or "").strip())
            png = _chart_to_png(ch)
            if png:
                pdf.chart_image(
                    png,
                    title,
                    insight,
                    charts_section=not charts_header_done,
                )
                charts_header_done = True
            else:
                if not charts_header_done:
                    pdf.h3(MAP_CHAT_PDF.SECTION.CHARTS)
                    charts_header_done = True
                pdf.h3(title)
                if insight:
                    pdf.caption(insight)


def _write_schema(pdf: _PDF, snap: dict):
    intro = _strip_md((snap.get("intro") or "").strip())
    fields = _strip_md((snap.get("fields") or "").strip())
    if not intro and not fields:
        return
    pdf.divider()
    pdf.h2(MAP_CHAT_PDF.SECTION.SCHEMA)
    if intro:
        pdf.body(intro)
    if fields:
        pdf.h3(MAP_CHAT_PDF.SECTION.FIELDS)
        pdf.body(fields)


def _last_user_message_text(messages: list[Any]) -> str:
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            return str(m.get("content") or "").strip()
    return ""


def _user_asks_about_one_project(user_text: str) -> bool:
    t = (user_text or "").strip().lower()
    if not t:
        return False
    if re.search(
        r"(?i)tell me about|what (can you tell me )?about|information (on|about)|details (on|about|for)",
        t,
    ) and re.search(r"(?i)project", t):
        return True
    if re.search(
        r"(?i)\b(show|describe|explain)\b.+\bproject\b",
        t,
    ):
        return True
    return False


def _looks_like_multi_project_inventory(sp: str) -> bool:
    s = (sp or "").strip()
    if not s:
        return False
    if re.search(
        r"(?i)found \d+\s+(projects|project results|matching|records)\b",
        s,
    ):
        return True
    if re.search(r"(?i)\bprojects identified\b|\bproject list\b", s[:1200]):
        return True
    return False


def _should_use_individual_project_hero(
    messages: list[Any],
    supplemental_project_attributes: list[tuple[str, str]] | None = None,
) -> bool:
    if supplemental_project_attributes:
        return True
    user_t = _last_user_message_text(messages)
    for m in reversed(messages):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        raw = (m.get("content") or "").strip()
        if not raw or raw == GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER:
            continue
        sp, sug = _split_geo_narrative(raw)
        if re.search(r"(?is)Project attributes\s*:", sp):
            return True
        if re.search(r"(?is)Found project\s+['\"]", raw):
            return True
        has_summary_heading = bool(
            re.search(r"(?im)^#{1,4}\s*Summary\b", sp)
            or re.search(r"\*\*Summary\*\*", sp[:1200])
        )
        if (
            sug.strip()
            and sp.strip()
            and not _looks_like_multi_project_inventory(sp)
        ):
            if has_summary_heading:
                return True
            if _user_asks_about_one_project(user_t):
                return True
    return False


def _project_title_from_summary_prose(sp: str) -> str | None:
    chunk = (sp or "").strip()[:2000]
    m = re.search(
        r"(?is)(?:the\s+)?([A-Z][A-Za-z0-9 ,'\-]{0,78}?)(?:\s+project\s+is|\s+Subdivision|\s+Drainage Improvements\b)",
        chunk,
    )
    if m:
        return m.group(1).strip()[:90]
    return None


def _extract_individual_project_name(
    messages: list[Any],
    supplemental_project_attributes: list[tuple[str, str]] | None = None,
) -> str:
    if supplemental_project_attributes:
        for k, v in supplemental_project_attributes:
            if str(k).strip().lower() == "name" and str(v).strip():
                return str(v).strip()[:90]
    for m in reversed(messages):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        raw = (m.get("content") or "").strip()
        if not raw or raw == GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER:
            continue
        sp, _ = _split_geo_narrative(raw)
        intro, rows, _ = _split_project_attributes_from_text(sp)
        for k, v in rows:
            if str(k).strip().lower() == "name" and str(v).strip():
                return str(v).strip()[:90]
        ma = re.search(r"Found project\s+['\"]([^'\"]+)['\"]", raw)
        if ma:
            return ma.group(1).strip()[:90]
        mb = re.search(r"Found project\s+['\"]([^'\"]+)['\"]", sp)
        if mb:
            return mb.group(1).strip()[:90]
        guess = _project_title_from_summary_prose(sp)
        if guess:
            return guess
    return "Project"


def _write_message(
    pdf: _PDF,
    role: str,
    content: str,
    geo_fmt: bool,
    *,
    omit_role_labels: bool = False,
    individual_project_pdf: bool = False,
    supplemental_attr_rows: list[tuple[str, str]] | None = None,
) -> None:
    raw = (content or "").strip()
    if not raw:
        return
    if not omit_role_labels:
        label = "You" if role == "user" else "Assistant"
        pdf.h2(label)
    elif role == "user":
        pdf.ln(2)
        pdf.body(_strip_md(raw))
        return
    if role == "assistant" and geo_fmt:
        if raw == GEO_CHAT_DEFERRED_ASSISTANT_PLACEHOLDER:
            pdf.caption(raw)
            return
        summary_part, sugg_part = _split_geo_narrative(raw)
        intro, attr_rows, attr_tail = _split_project_attributes_from_text(summary_part)
        if supplemental_attr_rows and len(attr_rows) == 0:
            attr_rows = list(supplemental_attr_rows)
        has_attrs = len(attr_rows) > 0
        narrative = intro if has_attrs else summary_part
        if individual_project_pdf and has_attrs:
            attr_lines = [f"{k}: {v}" for k, v in attr_rows]
            pdf.individual_project_results_attributes(attr_lines)
            if narrative.strip():
                pdf.section_spaced(MAP_CHAT_PDF.SECTION.SUMMARY)
                pdf.body(_strip_md(narrative.strip()))
        else:
            if narrative.strip():
                pdf.section_spaced(MAP_CHAT_PDF.SECTION.SUMMARY)
                pdf.body(_strip_md(narrative.strip()))
            if has_attrs:
                pdf.field_value_zebra_rows(attr_rows)
        if attr_tail.strip():
            pdf.caption(_strip_md(attr_tail.strip()))
        if sugg_part:
            lines = [ln.strip().lstrip("-* ") for ln in sugg_part.splitlines() if ln.strip()]
            pdf.numbered_followups(lines, section_title=MAP_CHAT_PDF.SECTION.FOLLOWUP)
        if not summary_part.strip() and not sugg_part:
            pdf.body(_strip_md(raw))
    else:
        pdf.body(_strip_md(raw))


def _build_legacy_pdf(
    messages: list[Any],
    geo_summary: dict | None,
    schema_snapshot: dict | None,
    data_source: str | None,
    supplemental_project_attributes: list[tuple[str, str]] | None = None,
) -> bytes:
    geo_fmt = data_source == "geo_lake_county"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    use_individual_hero = geo_fmt and _should_use_individual_project_hero(
        messages,
        supplemental_project_attributes,
    )
    if use_individual_hero:
        proj_title = _extract_individual_project_name(
            messages,
            supplemental_project_attributes,
        )
        pdf = _PDF(
            executive=True,
            banner_lead=MAP_CHAT_PDF.EXEC.INDIVIDUAL.BANNER_LEAD,
            banner_tail=MAP_CHAT_PDF.EXEC.BANNER.TAIL,
        )
        pdf.footer_left = _pdf_text(f"{proj_title} · Lake County")
        pdf.session_line = stamp
        pdf.hero_navy(proj_title, stamp, hero_copy=MAP_CHAT_PDF.EXEC.INDIVIDUAL)
    else:
        pdf = _PDF(executive=False)
        pdf.h1(MAP_CHAT_PDF.DOCUMENT.TITLE)
        pdf.caption(stamp)
        pdf.divider()

    last_assistant_i: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "assistant":
            last_assistant_i = i
            break

    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        sup = (
            supplemental_project_attributes
            if (
                last_assistant_i is not None
                and i == last_assistant_i
                and role == "assistant"
            )
            else None
        )
        _write_message(
            pdf,
            str(role),
            str(m.get("content") or ""),
            geo_fmt,
            omit_role_labels=use_individual_hero,
            individual_project_pdf=use_individual_hero,
            supplemental_attr_rows=sup,
        )

    _suppress_appendix = use_individual_hero or (
        geo_fmt
        and isinstance(geo_summary, dict)
        and geo_summary.get(GEO_RESULT_SUMMARY_UI_OMIT_RESULTS_DETAIL_KEY) is True
    )
    if isinstance(schema_snapshot, dict) and not _suppress_appendix:
        _write_schema(pdf, schema_snapshot)

    if geo_fmt and isinstance(geo_summary, dict) and not _suppress_appendix:
        _write_geo_summary_legacy(pdf, geo_summary)

    return bytes(pdf.output())


def build_map_chat_pdf_bytes(
    messages: list[Any],
    *,
    geo_summary: dict | None = None,
    schema_snapshot: dict | None = None,
    data_source: str | None = None,
    supplemental_project_attributes: list[tuple[str, str]] | None = None,
) -> bytes:
    geo_fmt = data_source == "geo_lake_county"
    rows = geo_summary.get("feature_rows") if isinstance(geo_summary, dict) else None
    _single_project_lookup = (
        isinstance(geo_summary, dict)
        and geo_summary.get(GEO_RESULT_SUMMARY_UI_OMIT_RESULTS_DETAIL_KEY) is True
    )
    if (
        geo_fmt
        and isinstance(geo_summary, dict)
        and isinstance(rows, list)
        and len(rows) > 0
        and not _single_project_lookup
    ):
        return _build_executive_geo_pdf(messages, geo_summary, schema_snapshot)
    return _build_legacy_pdf(
        messages,
        geo_summary,
        schema_snapshot,
        data_source,
        supplemental_project_attributes=supplemental_project_attributes,
    )


def build_single_response_pdf_bytes(
    user_content: str,
    assistant_content: str,
    *,
    geo_summary: dict | None = None,
    schema_snapshot: dict | None = None,
    data_source: str | None = None,
    supplemental_project_attributes: list[tuple[str, str]] | None = None,
) -> bytes:
    pair: list[dict[str, str]] = []
    if user_content and user_content.strip():
        pair.append({"role": "user", "content": user_content})
    pair.append({"role": "assistant", "content": assistant_content})
    return build_map_chat_pdf_bytes(
        pair,
        geo_summary=geo_summary,
        schema_snapshot=schema_snapshot,
        data_source=data_source,
        supplemental_project_attributes=supplemental_project_attributes,
    )
