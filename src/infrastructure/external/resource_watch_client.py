import httpx


class ResourceWatchClient:
    def __init__(self, auth_url: str, timeout: float = 10.0):
        self.auth_url = auth_url
        self.timeout = timeout

    async def get_user_info(self, token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.auth_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
