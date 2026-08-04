import httpx

from ai_travel_agent.utils.config import settings

SERPER_HEADERS = {
    "Content-Type": "application/json",
}


def _serper_headers() -> dict[str, str]:
    serper_key = settings.serper_api_key
    if not serper_key:
        raise RuntimeError("No SERPER_API_KEY configured")
    return {
        **SERPER_HEADERS,
        "X-API-KEY": serper_key,
    }


def web_search(
    query: str,
    num_results: int = 10,
) -> list[dict[str, str | None]]:
    resp = httpx.post(
        "https://google.serper.dev/search",
        headers=_serper_headers(),
        json={
            "q": query,
            "num": num_results,
        },
        timeout=10,
    )
    resp.raise_for_status()

    organic = resp.json().get("organic", [])

    return [
        {
            "title": r.get("title"),
            "snippet": r.get("snippet"),
            "link": r.get("link"),
        }
        for r in organic
    ]


def places_search(
    query: str,
    num_results: int = 10,
) -> list[dict[str, object]]:
    resp = httpx.post(
        "https://google.serper.dev/places",
        headers=_serper_headers(),
        json={
            "q": query,
            "num": num_results,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return list(resp.json().get("places") or [])
