from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


def _symbol_from_esri_payload(
    sym: dict,
) -> dict[str, object] | None:
    if not isinstance(sym, dict) or sym.get("type") != "esriPMS":
        return None
    b64 = sym.get("imageData")
    if not b64 or not isinstance(b64, str):
        return None
    w = int(sym.get("width") or 13)
    h = int(sym.get("height") or 21)
    yo = int(sym.get("yoffset") or 0)
    return {
        "dataUri": f"data:image/png;base64,{b64}",
        "width": w,
        "height": h,
        "yoffset": yo,
    }


def _unique_value_icons_from_renderer(r: dict) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for uvi in r.get("uniqueValueInfos") or []:
        if not isinstance(uvi, dict):
            continue
        val = uvi.get("value")
        if val is None:
            continue
        parsed = _symbol_from_esri_payload(uvi.get("symbol") or {})
        if parsed:
            out[str(val)] = parsed
    groups = r.get("uniqueValueGroups") or []
    for grp in groups:
        if not isinstance(grp, dict):
            continue
        for cls in grp.get("classes") or []:
            if not isinstance(cls, dict):
                continue
            for vlist in cls.get("values") or []:
                if not isinstance(vlist, list) or not vlist:
                    continue
                v0 = vlist[0]
                if v0 is None:
                    continue
                parsed = _symbol_from_esri_payload(cls.get("symbol") or {})
                if parsed:
                    out.setdefault(str(v0), parsed)
    return out


async def fetch_point_icons_for_class_field(
    client: ArcGISClient,
    layer_url: str,
    class_field: str,
    timeout: float,
) -> dict[str, dict[str, object]] | None:
    try:
        pjson = await client.get(layer_url, {"f": "pjson"}, timeout)
    except Exception as e:
        logger.warning(
            "arcgis_layer_pjson_failed",
            layer_url=layer_url,
            error=str(e),
        )
        return None
    r = (pjson.get("drawingInfo") or {}).get("renderer") or {}
    if r.get("type") != "uniqueValue":
        return None
    f1 = r.get("field1") or r.get("field")
    if str(f1 or "") != str(class_field):
        return None
    icons = _unique_value_icons_from_renderer(r)
    if not icons:
        return None
    ds = r.get("defaultSymbol")
    if isinstance(ds, dict):
        parsed = _symbol_from_esri_payload(ds)
        if parsed:
            icons["_default"] = parsed
    return icons
