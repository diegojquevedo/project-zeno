import json

import streamlit.components.v1 as components

from constants import (
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
        f"color:var(--text-color,#31333F);background:transparent;white-space:nowrap;"
        f"font-family:inherit"
    )
    components.html(
        f"""<script>
    (function() {{
    try {{
        var doc = window.parent.document;
        var id = {json.dumps(STREAMLIT_APP_TOP_BAR_TITLE_ELEMENT_ID)};
        if (doc.getElementById(id)) return;
        var el = doc.createElement("div");
        el.id = id;
        el.textContent = {json.dumps(STREAMLIT_APP_TOP_BAR_TITLE)};
        el.setAttribute("aria-hidden", "true");
        el.style.cssText = {json.dumps(top_bar_inline_style)};
        doc.body.appendChild(el);
    }} catch (e) {{}}
    }})();
    </script>""",
        width=1,
        height=1,
        scrolling=False,
    )
