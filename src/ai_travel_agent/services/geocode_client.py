from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ai-travel-agent/1.0"


@retry(wait=wait_fixed(1.1), stop=stop_after_attempt(3))
def geocode(query: str) -> dict[str, Any] | None:
    resp = httpx.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )

    resp.raise_for_status()
    data = resp.json()

    if not data:
        return None

    return {
        "lat": float(data[0]["lat"]),
        "lng": float(data[0]["lon"]),
        "display_name": data[0]["display_name"],
    }