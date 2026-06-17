"""FlightSearchTool — searches Google Flights via SerpApi."""

import os
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from serpapi.google_search import GoogleSearch

from ai_travel_agent.models import FlightOption, FlightSegment
from ai_travel_agent.tools.base import BaseTravelTool
from ai_travel_agent.utils.config import settings
from ai_travel_agent.utils.exceptions import (
    APIAuthError,
    APIRateLimitError,
    NoResultsError,
)


class FlightSearchInput(BaseModel):
    origin: str = Field(..., description="IATA airport code e.g. BOM, JFK, CDG")
    destination: str = Field(..., description="IATA airport code e.g. CDG, LHR, NRT")
    departure_date: str = Field(..., description="YYYY-MM-DD")
    return_date: str | None = Field(None, description="YYYY-MM-DD — omit for one-way")
    adults: int = Field(default=1, ge=1, le=9)
    max_price: float | None = Field(None, description="Max total price in USD")
    max_stops: int | None = Field(
        None, ge=0, description="0=nonstop only, 1=one stop max"
    )
    travel_class: int = Field(
        default=1, description="1=economy 2=premium economy 3=business 4=first"
    )


class FlightSearchTool(BaseTravelTool):
    name: str = "flight_search"
    description: str = (
        "Search for available flights between two airports using IATA codes. "
        "Returns up to 5 options sorted by price. "
        "Supports filtering by max price, max stops, and travel class."
    )
    args_schema: type[BaseModel] = FlightSearchInput
    cache_namespace: str = "flights"
    cache_ttl: int = settings.cache_ttl_flights

    # ------------------------------------------------------------------
    # BaseTool required entry point
    # ------------------------------------------------------------------

    def _run(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        max_price: float | None = None,
        max_stops: int | None = None,
        travel_class: int = 1,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": departure_date,
            "return_date": return_date,
            "adults": adults,
            "travel_class": travel_class,
        }
        results = self._execute_with_cache(params)

        # client-side filters applied after cache so cached data is reusable
        if max_price is not None:
            results = [r for r in results if r["total_price_usd"] <= max_price]
        if max_stops is not None:
            results = [r for r in results if r["num_stops"] <= max_stops]

        results.sort(key=lambda r: r["total_price_usd"])
        return results[:5]

    # ------------------------------------------------------------------
    # Real API call
    # ------------------------------------------------------------------

    def _fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        origin: str = kwargs["origin"]
        destination: str = kwargs["destination"]
        departure_date: str = kwargs["departure_date"]
        return_date: str | None = kwargs.get("return_date")
        adults: int = kwargs.get("adults", 1)
        travel_class: int = kwargs.get("travel_class", 1)
        trip_type = 1 if return_date else 2

        serpapi_params: dict[str, Any] = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date,
            "type": trip_type,
            "adults": adults,
            "travel_class": travel_class,
            "currency": "USD",
            "hl": "en",
            "api_key": os.getenv("SERPAPI_API_KEY") or settings.serper_api_key,
        }
        if return_date:
            serpapi_params["return_date"] = return_date

        search = GoogleSearch(serpapi_params)
        response: dict[str, Any] = search.get_dict()

        if "error" in response:
            err = str(response["error"])
            if any(k in err.lower() for k in ["rate", "limit", "429"]):
                raise APIRateLimitError(retry_after=60)
            if any(k in err.lower() for k in ["invalid", "key", "401", "403"]):
                raise APIAuthError(f"SerpApi key error: {err}")
            raise Exception(f"SerpApi Flights error: {err}")

        all_flights: list[dict[str, Any]] = response.get("best_flights", []) + response.get(
            "other_flights", []
        )

        if not all_flights:
            raise NoResultsError(f"{origin}→{destination} on {departure_date}")

        return [self._map_flight(f) for f in all_flights]

    # ------------------------------------------------------------------
    # Response mapping → your FlightOption / FlightSegment models
    # ------------------------------------------------------------------

    def _map_flight(self, raw: dict[str, Any]) -> dict[str, Any]:
        segments: list[FlightSegment] = []
        for seg in raw.get("flights", []):
            dep = seg["departure_airport"]
            arr = seg["arrival_airport"]
            segments.append(
                FlightSegment(
                    departure_airport=dep["id"],
                    arrival_airport=arr["id"],
                    departure_time=self._parse_dt(dep["time"]),
                    arrival_time=self._parse_dt(arr["time"]),
                    airline=seg.get("airline", ""),
                    flight_number=seg.get("flight_number", ""),
                    duration_minutes=int(seg.get("duration", 0)),
                )
            )

        price = float(raw.get("price", 0))
        cabin = ""
        if segments:
            cabin = raw.get("flights", [{}])[0].get("travel_class", "Economy")

        # FlightOption.amadeus_offer_id repurposed to store SerpApi booking token
        option = FlightOption(
            id=str(uuid.uuid4()),
            segments=segments,
            total_price_usd=price,
            currency="USD",
            cabin_class=cabin or "Economy",
            amadeus_offer_id=raw.get("booking_token", ""),
        )
        result = option.model_dump()
        # add computed fields consumed by filters / UI
        result["num_stops"] = option.num_stops
        result["total_duration_minutes"] = option.total_duration_minutes
        result["airline_logo"] = (
            raw.get("flights", [{}])[0].get("airline_logo", "")
            if raw.get("flights")
            else ""
        )
        return result

    @staticmethod
    def _parse_dt(raw: str) -> datetime:
        """Parse '2025-12-10 14:30' → datetime. Falls back to now() on bad input."""
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return datetime.now()

    # ------------------------------------------------------------------
    # Mock data — realistic fallback, same schema as real response
    # ------------------------------------------------------------------

    def _mock_data(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        if len(args) >= 3:
            origin, destination, departure_date = args[:3]
        else:
            origin = kwargs["origin"]
            destination = kwargs["destination"]
            departure_date = kwargs["departure_date"]

        rows = [
            ("AI 131", "Air India", 742, 510, 0),
            ("EK 505", "Emirates", 820, 570, 1),
            ("QR 556", "Qatar Airways", 890, 540, 1),
            ("BA 119", "British Airways", 960, 480, 0),
            ("LH 760", "Lufthansa", 1050, 600, 1),
        ]
        results: list[dict[str, Any]] = []
        for flight_no, airline, price, dur, stops in rows:
            seg = FlightSegment(
                departure_airport=origin,
                arrival_airport=destination,
                departure_time=datetime.strptime(
                    f"{departure_date} 10:00", "%Y-%m-%d %H:%M"
                ),
                arrival_time=datetime.strptime(
                    f"{departure_date} 18:30", "%Y-%m-%d %H:%M"
                ),
                airline=airline,
                flight_number=flight_no,
                duration_minutes=dur,
            )
            option = FlightOption(
                id=str(uuid.uuid4()),
                segments=[seg],
                total_price_usd=float(price),
                currency="USD",
                cabin_class="Economy",
                amadeus_offer_id="",
            )
            row = option.model_dump()
            row["num_stops"] = stops
            row["total_duration_minutes"] = dur
            row["airline_logo"] = ""
            results.append(row)
        return results
