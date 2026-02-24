import httpx

_client: httpx.AsyncClient | None = None


def get_analytics_client() -> httpx.AsyncClient:
    """Return a shared AsyncClient for Analytics API with connection pooling."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
            timeout=httpx.Timeout(60.0),
        )
    return _client
