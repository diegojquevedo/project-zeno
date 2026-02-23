import json
from typing import Any, Optional

import httpx


class ArcGISClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    async def get(
        self, query_url: str, params: dict, timeout: Optional[float] = None
    ) -> dict[str, Any]:
        t = timeout if timeout is not None else self.timeout
        p = dict(params)
        if self.api_key and "token" not in p:
            p["token"] = self.api_key
        async with httpx.AsyncClient(timeout=t) as client:
            resp = await client.get(query_url, params=p)
            resp.raise_for_status()
            return resp.json()

    async def post(
        self, query_url: str, data: dict, timeout: Optional[float] = None
    ) -> dict[str, Any]:
        t = timeout if timeout is not None else self.timeout
        d = dict(data)
        if self.api_key and "token" not in d:
            d["token"] = self.api_key
        async with httpx.AsyncClient(timeout=t) as client:
            resp = await client.post(query_url, data=d)
            resp.raise_for_status()
            return resp.json()

    async def query_bbox(
        self,
        query_url: str,
        minx: float,
        miny: float,
        maxx: float,
        maxy: float,
        out_sr: int = 4326,
        in_sr: int = 4326,
    ) -> dict[str, Any]:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": out_sr,
            "inSR": in_sr,
            "f": "geojson",
            "geometry": json.dumps(
                {"xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy}
            ),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
        }
        return await self.get(query_url, params)
