from typing import Any

import httpx

from ai_travel_agent.services.search_client import places_search
from ai_travel_agent.utils.config import settings

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"


def places_text_search(
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    api_key = settings.google_places_api_key

    if not api_key:
        return _serper_places_text_search(query, max_results)

    response = httpx.post(
        PLACES_URL,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.displayName,"
                "places.formattedAddress,"
                "places.location,"
                "places.rating,"
                "places.userRatingCount,"
                "places.priceLevel,"
                "places.websiteUri,"
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
                "ratingCount": place.get("userRatingCount"),
                "price_level": _map_price_level(place.get("priceLevel")),
                "address": place.get("formattedAddress"),
                "website": place.get("websiteUri"),
                "types": place.get("types", []),
            }
        )

    return results


def _serper_places_text_search(
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    results = []
    for place in places_search(query, num_results=max_results):
        results.append(
            {
                "name": place.get("title") or place.get("name"),
                "lat": place.get("latitude") or place.get("lat"),
                "lng": place.get("longitude") or place.get("lng"),
                "rating": place.get("rating"),
                "price_level": _map_price_level(place.get("priceLevel")),
                "address": place.get("address"),
                "types": [place.get("category")] if place.get("category") else [],
                "website": place.get("website"),
                "phone": place.get("phoneNumber"),
                "rating_count": place.get("ratingCount") or place.get("reviews"),
            }
        )
    return results


def _map_price_level(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    if "$" in text:
        return max(0, min(3, text.count("$") - 1))
    if text.startswith("PRICE_LEVEL_"):
        mapping = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4,
        }
        return mapping.get(text)
    return None


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
