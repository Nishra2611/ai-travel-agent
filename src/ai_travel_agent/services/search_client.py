import httpx

from ai_travel_agent.utils.config import settings


def web_search(
    query: str,
    num_results: int = 10,
) -> list[dict[str, str | None]]:
    serper_key = settings.serper_api_key

    if serper_key:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": serper_key,
                "Content-Type": "application/json",
            },
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

    raise RuntimeError("No SERPER_API_KEY configured")
