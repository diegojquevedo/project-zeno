import json

import streamlit.components.v1 as components

from constants import (
    GEO_HTML_THEME_DARK_CLASS,
    GEO_MAP_ST_HEADER_REM,
    STREAMLIT_APP_TOP_BAR_TITLE,
    STREAMLIT_APP_TOP_BAR_TITLE_ELEMENT_ID,
    STREAMLIT_APP_TOP_BAR_TITLE_FONT_SIZE,
    STREAMLIT_APP_TOP_BAR_TITLE_PAD_LEFT,
)


def render_main_header() -> None:
    top_bar_inline_style = (
        f"position:fixed;top:0;left:80px;right:0;height:{GEO_MAP_ST_HEADER_REM};"
        f"box-sizing:border-box;margin:0;padding:0 0 0 {STREAMLIT_APP_TOP_BAR_TITLE_PAD_LEFT};"
        f"display:flex;align-items:center;z-index:2147483647;pointer-events:none;"
        f"font-weight:600;line-height:1.4;font-size:{STREAMLIT_APP_TOP_BAR_TITLE_FONT_SIZE};"
        f"background:transparent;white-space:nowrap;"
        f"font-family:inherit"
    )
    components.html(
        f"""<script>
    (function() {{
    try {{
        var doc = window.parent.document;
        var id = {json.dumps(STREAMLIT_APP_TOP_BAR_TITLE_ELEMENT_ID)};
        var moKey = "__geoAiTitleBarMo";
        function parseRgb(bg) {{
            var m = bg.match(
                /rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*(?:,\\s*([\\d.]+)\\s*)?\\)/
            );
            if (!m) return null;
            var alpha = m[4] !== undefined ? parseFloat(m[4]) : 1;
            return {{ r: +m[1], g: +m[2], b: +m[3], a: alpha }};
        }}
        function effectiveBgRgb(startEl) {{
            var cur = startEl;
            while (cur) {{
                var p = parseRgb(window.getComputedStyle(cur).backgroundColor);
                if (p && p.a > 0.08) return {{ r: p.r, g: p.g, b: p.b }};
                cur = cur.parentElement;
            }}
            var bp = parseRgb(window.getComputedStyle(doc.body).backgroundColor);
            if (bp && bp.a > 0.08) return {{ r: bp.r, g: bp.g, b: bp.b }};
            return {{ r: 255, g: 255, b: 255 }};
        }}
        function titleColorForRgb(rgb) {{
            var y = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
            return y > 0.45 ? "#111827" : "#ffffff";
        }}
        var darkClass = {json.dumps(GEO_HTML_THEME_DARK_CLASS)};
        function syncGeoThemeDarkClass() {{
            var root = doc.querySelector('[data-testid="stAppViewContainer"]');
            var html = doc.documentElement;
            if (!root) return;
            var rgb = effectiveBgRgb(root);
            var y = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
            if (y <= 0.45) html.classList.add(darkClass);
            else html.classList.remove(darkClass);
        }}
        var debounce = null;
        function syncTitleColor() {{
            var el = doc.getElementById(id);
            var root = doc.querySelector('[data-testid="stAppViewContainer"]');
            if (!el || !root) return;
            el.style.color = titleColorForRgb(effectiveBgRgb(root));
        }}
        function scheduleSync() {{
            if (debounce) clearTimeout(debounce);
            debounce = setTimeout(function() {{
                syncGeoThemeDarkClass();
                syncTitleColor();
            }}, 40);
        }}
        var el = doc.getElementById(id);
        if (!el) {{
            el = doc.createElement("div");
            el.id = id;
            el.textContent = {json.dumps(STREAMLIT_APP_TOP_BAR_TITLE)};
            el.setAttribute("aria-hidden", "true");
            el.style.cssText = {json.dumps(top_bar_inline_style)};
            doc.body.appendChild(el);
        }}
        syncGeoThemeDarkClass();
        syncTitleColor();
        if (doc[moKey]) doc[moKey].disconnect();
        doc[moKey] = new MutationObserver(scheduleSync);
        doc[moKey].observe(doc.body, {{
            subtree: true,
            childList: true,
            attributes: true,
            attributeFilter: ["class", "style", "data-theme"]
        }});
    }} catch (e) {{}}
    }})();
    </script>""",
        width=1,
        height=1,
        scrolling=False,
    )
