from typing import Any

import httpx

from ai_travel_agent.utils.config import settings

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"


def places_text_search(
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    api_key = settings.google_places_api_key

    if not api_key:
        return []

    response = httpx.post(
        PLACES_URL,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.displayName,"
                "places.formattedAddress,"
                "places.location,"
                "places.rating,"
                "places.priceLevel,"
                "places.types"
            ),
        },
        json={
            "textQuery": query,
        },
        timeout=10,
    )
    response.raise_for_status()

    results = []

    for place in response.json().get("places", [])[:max_results]:
        results.append(
            {
                "name": place.get("displayName", {}).get("text"),
                "lat": place.get("location", {}).get("latitude"),
                "lng": place.get("location", {}).get("longitude"),
                "rating": place.get("rating"),
                "price_level": place.get("priceLevel"),
                "address": place.get("formattedAddress"),
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

    if isinstance(rating, int | float):
        return float(rating)

    return None
