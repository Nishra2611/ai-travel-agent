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

        results = places_text_search(query, max_results=30)

        if not results:
            return self._mock_restaurants(city, cuisine, limit)

        target_price = BUDGET_TO_PRICE_LEVEL.get(budget) if budget else None

        filtered: list[dict[str, Any]] = [
            r for r in results
            if r.get("rating") is not None
            and float(r["rating"]) >= min_rating
            and (target_price is None or r.get("price_level") in (target_price, None))
        ]

        filtered.sort(key=lambda item: float(item["rating"]), reverse=True)
        return filtered[:limit]

    def _mock_restaurants(self, city: str, cuisine: str | None, limit: int) -> list[dict[str, Any]]:
        tag = f"{cuisine.title()} " if cuisine else ""
        rows = [
            (f"{tag}Le Gourmet", 4.8, "$$", "12 Rue de Rivoli"),
            (f"{tag}Bistro Central", 4.6, "$", "34 Avenue des Champs"),
            (f"{tag}The Grand Table", 4.5, "$$$", "8 Rue Saint-Honoré"),
            (f"{tag}Café du Marché", 4.4, "$", "22 Rue du Faubourg"),
            (f"{tag}Chez Michel", 4.3, "$$", "5 Boulevard Haussmann"),
            (f"{tag}La Terrasse", 4.2, "$$", "17 Rue de la Paix"),
            (f"{tag}Spice Garden", 4.1, "$$", "9 Rue Montmartre"),
            (f"{tag}Urban Kitchen", 4.0, "$", "44 Rue du Temple"),
        ]
        return [
            {
                "name": f"{name} {city}",
                "lat": 48.85 + i * 0.01,
                "lng": 2.35 + i * 0.01,
                "rating": rating,
                "price_level": price,
                "address": f"{address}, {city}",
                "types": ["restaurant"],
            }
            for i, (name, rating, price, address) in enumerate(rows[:limit])
        ]
