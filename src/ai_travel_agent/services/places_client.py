import os
from typing import Any

import httpx

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


def places_text_search(
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")

    if not api_key:
        return []

    response = httpx.get(
        PLACES_URL,
        params={
            "query": query,
            "key": api_key,
        },
        timeout=10,
    )

    response.raise_for_status()

    results: list[dict[str, Any]] = []

    for place in response.json().get("results", [])[:max_results]:
        results.append(
            {
                "name": place.get("name"),
                "lat": place.get("geometry", {}).get("location", {}).get("lat"),
                "lng": place.get("geometry", {}).get("location", {}).get("lng"),
                "rating": place.get("rating"),
                "price_level": place.get("price_level"),
                "address": place.get("formatted_address"),
                "types": place.get("types", []),
            }
        )

    return results


def find_place_rating(
    name: str,
    city: str,
) -> float | None:
    results = places_text_search(
        f"{name} {city}",
        max_results=1,
    )

    if not results:
        return None

    rating = results[0].get("rating")

    if isinstance(rating, (int, float)):
        return float(rating)

    return None
