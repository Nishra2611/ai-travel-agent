"""HotelSearchTool — searches Google Hotels via SerpApi."""

import os
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field
from serpapi import GoogleSearch

from ai_travel_agent.models import GeoLocation, HotelOption
from ai_travel_agent.tools.base import BaseTravelTool
from ai_travel_agent.utils.config import settings
from ai_travel_agent.utils.exceptions import (
    APIAuthError,
    APIRateLimitError,
    NoResultsError,
)


class HotelSearchInput(BaseModel):
    city: str = Field(..., description="City name e.g. Paris, Tokyo, Bali")
    check_in: str = Field(..., description="YYYY-MM-DD")
    check_out: str = Field(..., description="YYYY-MM-DD")
    adults: int = Field(default=2, ge=1, le=9)
    max_price_per_night: float | None = Field(None, description="Max USD per night")
    min_rating: float | None = Field(
        None, ge=0.0, le=5.0, description="Min star rating"
    )
    hotel_class: str | None = Field(
        None, description="Star class filter e.g. '4,5' for 4 and 5 star"
    )


class HotelSearchTool(BaseTravelTool):
    name: str = "hotel_search"
    description: str = (
        "Search for hotels in a city for given dates. "
        "Returns up to 10 options sorted by rating then price. "
        "Supports filtering by min star rating and max price per night."
    )
    args_schema: type[BaseModel] = HotelSearchInput
    cache_namespace: str = "hotels"
    cache_ttl: int = settings.cache_ttl_hotels

    # ------------------------------------------------------------------
    # BaseTool required entry point
    # ------------------------------------------------------------------

    def _run(
        self,
        city: str,
        check_in: str,
        check_out: str,
        adults: int = 2,
        max_price_per_night: float | None = None,
        min_rating: float | None = None,
        hotel_class: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "city": city.lower().strip(),
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "hotel_class": hotel_class,
        }
        results = self._execute_with_cache(params)

        # client-side filters — applied after cache
        if min_rating is not None:
            results = [
                h
                for h in results
                if h.get("star_rating") is not None and h["star_rating"] >= min_rating
            ]
        if max_price_per_night is not None:
            results = [
                h for h in results if h["price_per_night_usd"] <= max_price_per_night
            ]

        # sort: highest rating first, then cheapest
        results.sort(
            key=lambda h: (-(h.get("star_rating") or 0.0), h["price_per_night_usd"])
        )
        return results[:10]

    # ------------------------------------------------------------------
    # Real API call
    # ------------------------------------------------------------------

    def _fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        city: str = kwargs["city"]
        check_in: str = kwargs["check_in"]
        check_out: str = kwargs["check_out"]
        adults: int = kwargs.get("adults", 2)
        hotel_class: str | None = kwargs.get("hotel_class")
        serpapi_params: dict[str, Any] = {
            "engine": "google_hotels",
            "q": f"{city} hotels",
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adults,
            "currency": "USD",
            "gl": "us",
            "hl": "en",
            "api_key": os.getenv("SERPAPI_API_KEY") or settings.serper_api_key,
        }
        if hotel_class:
            serpapi_params["hotel_class"] = hotel_class

        search = GoogleSearch(serpapi_params)
        response: dict[str, Any] = search.get_dict()

        if "error" in response:
            err = str(response["error"])
            if any(k in err.lower() for k in ["rate", "limit", "429"]):
                raise APIRateLimitError(retry_after=60)
            if any(k in err.lower() for k in ["invalid", "key", "401", "403"]):
                raise APIAuthError(f"SerpApi key error: {err}")
            raise Exception(f"SerpApi Hotels error: {err}")

        properties: list[dict[str, Any]] = response.get("properties", [])
        if not properties:
            raise NoResultsError(f"No hotels found in {city}")

        ci = date.fromisoformat(check_in)
        co = date.fromisoformat(check_out)
        nights = max((co - ci).days, 1)

        return [self._map_hotel(p, check_in, check_out, nights) for p in properties]

    # ------------------------------------------------------------------
    # Response mapping → your HotelOption / GeoLocation models
    # ------------------------------------------------------------------

    def _map_hotel(
        self, prop: dict[str, Any], check_in: str, check_out: str, nights: int
    ) -> dict[str, Any]:
        rate_info = prop.get("rate_per_night", {})
        # always use extracted_ (numeric) — "lowest" is a display string
        per_night = float(rate_info.get("extracted_lowest") or 0)

        total_info = prop.get("total_rate", {})
        total = float(total_info.get("extracted_lowest") or per_night * nights)

        # parse "5-star hotel" → 5.0
        star_str: str = prop.get("hotel_class", "")
        try:
            stars: float | None = float(star_str.split("-")[0]) if star_str else None
        except (ValueError, IndexError):
            stars = None

        coords = prop.get("coordinates", {})
        lat = float(coords.get("latitude") or 0.0)
        lng = float(coords.get("longitude") or 0.0)

        images = prop.get("images", [])
        thumbnail: str = images[0].get("thumbnail", "") if images else ""

        option = HotelOption(
            id=prop.get("property_token") or str(uuid.uuid4()),
            name=prop.get("name", "Unknown Hotel"),
            star_rating=stars,
            price_per_night_usd=per_night,
            total_price_usd=total,
            check_in=date.fromisoformat(check_in),
            check_out=date.fromisoformat(check_out),
            location=GeoLocation(latitude=lat, longitude=lng),
            address=prop.get("link", ""),
            amenities=prop.get("amenities", []),
            review_score=prop.get("overall_rating"),
            review_count=prop.get("reviews"),
            booking_url=prop.get("link", ""),
        )
        result = option.model_dump()
        # extra fields not in schema but useful for UI / later tools
        result["thumbnail"] = thumbnail
        result["nearby_places"] = prop.get("nearby_places", [])
        result["eco_certified"] = prop.get("eco_certified", False)
        result["check_in_time"] = prop.get("check_in_time", "")
        result["check_out_time"] = prop.get("check_out_time", "")
        return result

    # ------------------------------------------------------------------
    # Mock data — realistic fallback, same schema as real response
    # ------------------------------------------------------------------

    def _mock_data(self, **kwargs: Any) -> list[dict[str, Any]]:
        city: str = kwargs["city"]
        check_in: str = kwargs["check_in"]
        check_out: str = kwargs["check_out"]
        ci = date.fromisoformat(check_in)
        co = date.fromisoformat(check_out)
        nights = max((co - ci).days, 1)

        rows = [
            (
                "Grand Palace Hotel",
                5,
                4.8,
                320,
                ["Free Wi-Fi", "Pool", "Spa", "Gym", "Breakfast"],
            ),
            (
                "Boutique Art House",
                4,
                4.6,
                180,
                ["Free Wi-Fi", "Breakfast", "Rooftop Bar"],
            ),
            ("City Loft Suites", 4, 4.4, 155, ["Free Wi-Fi", "Gym", "Kitchenette"]),
            ("Riverside Garden", 4, 4.3, 140, ["Free Wi-Fi", "Pool", "Garden"]),
            (
                "Heritage Quarter",
                4,
                4.5,
                165,
                ["Free Wi-Fi", "Spa", "Historic Building"],
            ),
            ("Le Petit Hotel", 3, 4.1, 95, ["Free Wi-Fi", "Breakfast"]),
            ("Urban Stay Express", 3, 3.9, 80, ["Free Wi-Fi"]),
            (
                "Skyline View Hotel",
                5,
                4.7,
                290,
                ["Free Wi-Fi", "Pool", "Gym", "Spa", "Bar"],
            ),
            ("The Cloister Inn", 3, 4.0, 110, ["Free Wi-Fi", "Breakfast", "Garden"]),
            ("Nomad Capsule Hotel", 2, 3.7, 45, ["Free Wi-Fi", "Shared Kitchen"]),
        ]
        results: list[dict[str, Any]] = []
        for i, (name, stars, rating, ppn, amenities) in enumerate(rows):
            option = HotelOption(
                id=f"mock-{uuid.uuid4().hex[:8]}",
                name=f"{name} {city.title()}",
                star_rating=float(stars),
                price_per_night_usd=float(ppn),
                total_price_usd=float(ppn * nights),
                check_in=ci,
                check_out=co,
                location=GeoLocation(
                    latitude=round(48.8566 + i * 0.008, 4),
                    longitude=round(2.3522 + i * 0.006, 4),
                ),
                address=f"{10 + i * 12} Main Street, {city.title()}",
                amenities=amenities,
                review_score=rating,
                review_count=400 + i * 200,
                booking_url="",
            )
            row = option.model_dump()
            row["thumbnail"] = ""
            row["nearby_places"] = []
            row["eco_certified"] = i % 3 == 0
            row["check_in_time"] = "3:00 PM"
            row["check_out_time"] = "12:00 PM"
            results.append(row)
        return results
