from typing import Annotated

import cachetools
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command

from src.api.geo_lake_county_config import (
    get_geo_lake_county_layer_by_id,
    get_geo_lake_county_layers,
)
from src.api.lake_county_constants import HTTP_TIMEOUT_DOMAINS
from src.infrastructure.external.arcgis_client import ArcGISClient
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

SCHEMA_CACHE_TTL = 3600
_schema_cache: cachetools.TTLCache = cachetools.TTLCache(
    maxsize=64, ttl=SCHEMA_CACHE_TTL
)


def _arcgis_client() -> ArcGISClient:
    return ArcGISClient(api_key=None, timeout=HTTP_TIMEOUT_DOMAINS)


def _format_schema_summary(data: dict) -> str:
    lines = []
    name = data.get("name", "Unknown")
    geom_type = data.get("geometryType", "Unknown")
    lines.append(f"# Schema: {name}")
    lines.append(f"**Geometry type:** {geom_type}")
    lines.append("")
    fields = data.get("fields", [])
    if fields:
        lines.append("## Fields")
        for f in fields:
            fn = f.get("name", "")
            if fn and fn.upper() in ("SHAPE", "SHAPE_LENGTH", "SHAPE_AREA"):
                continue
            alias = f.get("alias", fn)
            ftype = f.get("type", "")
            domain = f.get("domain")
            domain_info = ""
            if domain:
                dtype = domain.get("type", "")
                if dtype == "codedValue":
                    vals = domain.get("codedValues", [])
                    codes = [f"{v.get('code')} ({v.get('name', '')})" for v in vals[:10]]
                    domain_info = f" [domain: {', '.join(codes)}{'...' if len(vals) > 10 else ''}]"
                elif dtype == "range":
                    r = domain.get("range", [])
                    domain_info = f" [range: {r}]"
            lines.append(f"- **{fn}** ({ftype}): {alias}{domain_info}")
    return "\n".join(lines)


async def _fetch_layer_schema(layer_url: str) -> dict | None:
    if layer_url in _schema_cache:
        return _schema_cache[layer_url]
    client = _arcgis_client()
    try:
        data = await client.get(layer_url, {"f": "json"}, HTTP_TIMEOUT_DOMAINS)
    except Exception as e:
        logger.warning("geo_discover_schema_failed", url=layer_url, error=str(e))
        return None
    if data.get("error"):
        return None
    _schema_cache[layer_url] = data
    return data


@tool("geo_discover_layer_schema")
async def geo_discover_layer_schema(
    layer_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Fetch ArcGIS layer schema (fields, geometry type, domains) for a layer.
    Use when data_source is geo_lake_county and you need to understand a layer's structure
    to answer the user. layer_id: a configured layer id (check available layer ids in context).
    Returns raw fields, types, aliases, and domain values — analyze to deduce which field
    to use for filtering based on the user's question.
    """
    tid = tool_call_id or ""
    layer = get_geo_lake_county_layer_by_id(layer_id)
    if not layer:
        available = [layer["layer_id"] for layer in get_geo_lake_county_layers()]
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Layer '{layer_id}' not found. Available: {', '.join(available)}",
                        tool_call_id=tid,
                    )
                ],
            },
        )
    url = layer.get("arcgis_url")
    if not url:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Layer '{layer_id}' has no URL configured.",
                        tool_call_id=tid,
                    )
                ],
            },
        )
    data = await _fetch_layer_schema(url)
    if not data:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Failed to fetch schema for layer '{layer_id}' from ArcGIS.",
                        tool_call_id=tid,
                    )
                ],
            },
        )
    summary = _format_schema_summary(data)
    return Command(
        update={
            "messages": [
                ToolMessage(content=summary, tool_call_id=tid),
            ],
        },
    )
