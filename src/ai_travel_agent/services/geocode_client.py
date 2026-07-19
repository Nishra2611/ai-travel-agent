from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ai-travel-agent/1.0"


@retry(
    retry=retry_if_exception_type(httpx.HTTPStatusError),
    wait=wait_fixed(1.1),
    stop=stop_after_attempt(3),
)
def geocode(query: str) -> dict[str, Any] | None:
    try:
        resp = httpx.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException):
        return None

    data = resp.json()

    if not data:
        return None

    return {
        "lat": float(data[0]["lat"]),
        "lng": float(data[0]["lon"]),
        "display_name": data[0]["display_name"],
    }
