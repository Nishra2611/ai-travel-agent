import os

import httpx


def web_search(
    query: str,
    num_results: int = 10,
) -> list[dict[str, str | None]]:
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
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

    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": tavily_key, "query": query, "max_results": num_results},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            {"title": r.get("title"), "snippet": r.get("content"), "link": r.get("url")}
            for r in resp.json().get("results", [])
        ]

    raise RuntimeError("No SERPER_API_KEY or TAVILY_API_KEY configured")
