from geo_feature_display_constants import (
    GEO_ROW_ID_FALLBACK_KEYS,
    GEO_ROW_LABEL_KEYS,
)


def geo_feature_row_display_label(row: dict | None) -> str:
    if not isinstance(row, dict):
        return "\u2014"
    for nk in GEO_ROW_LABEL_KEYS:
        nv = row.get(nk)
        if nv is not None and str(nv).strip():
            return str(nv).strip()
    pid = row.get("project_id")
    if pid is not None and str(pid).strip():
        return str(pid).strip()
    return "\u2014"


def geo_feature_row_display_id(row: dict | None) -> object | str:
    if not isinstance(row, dict):
        return "\u2014"
    for nk in GEO_ROW_ID_FALLBACK_KEYS:
        nv = row.get(nk)
        if nv is not None and str(nv).strip():
            return nv
    return "\u2014"
