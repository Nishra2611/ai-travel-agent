from typing import Any

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ai_travel_agent.services.geocode_client import geocode
from ai_travel_agent.services.search_client import web_search

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def overpass_attractions_near(
    lat: float,
    lng: float,
    radius_m: int = 8000,
    limit: int = 25,
) -> list[dict[str, Any]]:
    query = f"""
    [out:json][timeout:25];
    (
      node["tourism"~"attraction|museum|gallery|zoo|theme_park|viewpoint"](around:{radius_m},{lat},{lng});
      node["leisure"~"park|garden"](around:{radius_m},{lat},{lng});
    );
    out body {limit};
    """

    resp = httpx.post(
        OVERPASS_URL,
        data={"data": query},
        headers={
            "User-Agent": "ai-travel-agent/1.0",
            "Accept": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()

    results: list[dict[str, Any]] = []

    for el in resp.json().get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")

        if not name:
            continue

        results.append(
            {
                "name": name,
                "lat": el.get("lat"),
                "lng": el.get("lon"),
                "category": tags.get("tourism") or tags.get("leisure"),
                "hours": tags.get("opening_hours"),
            }
        )

    return results


class AttractionFinderInput(BaseModel):
    city: str = Field(
        ...,
        description="City to search attractions in",
    )
    country: str | None = Field(
        default=None,
        description="Optional country name",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=20,
    )


class AttractionFinderTool(BaseTool):
    name: str = "attraction_finder"
    description: str = (
        "Find tourist attractions in a city with coordinates and opening hours."
    )
    args_schema: type[BaseModel] = AttractionFinderInput

    def _run(
        self,
        city: str,
        country: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self._find(city, country, limit)

    async def _arun(
        self,
        city: str,
        country: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self._find(city, country, limit)

    def _find(
        self,
        city: str,
        country: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        query = f"{city}, {country}" if country else city

        center = geocode(query)

        if center is None:
            return []

        candidates = overpass_attractions_near(
            float(center["lat"]),
            float(center["lng"]),
        )

        web_hits = web_search(
            f"top tourist attractions in {city}",
            num_results=15,
        )

        web_titles = " ".join(
            str(hit["title"]).lower() for hit in web_hits if hit.get("title")
        )

        for attraction in candidates:
            attraction["popularity_hint"] = (
                str(attraction["name"]).lower() in web_titles
            )

            # Day 2 will replace this with Google Places ratings
            attraction["rating"] = None

        candidates.sort(
            key=lambda item: bool(item.get("popularity_hint")),
            reverse=True,
        )

        return candidates[:limit]
