"""
PlanResponse now includes the itinerary field.
New endpoint: GET /api/plan/{session_id}/itinerary
  Returns just the day-by-day Itinerary for a completed session.
All existing endpoints are unchanged.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.dummy_tool import DummyFlightTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.tools.restaurant_finder import RestaurantFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool
from ai_travel_agent.utils.cache import cache

app = FastAPI(title="AI Travel Agent", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

flight_tool = DummyFlightTool()
hotel_tool = HotelSearchTool()
_attraction_tool = AttractionFinderTool()
_restaurant_tool = RestaurantFinderTool()
_weather_tool = WeatherCheckerTool()
_budget_tool = BudgetTrackerTool()

_agent = None


def _get_agent() -> Any:
    global _agent
    if _agent is None:
        from ai_travel_agent.agents.graph import build_graph

        _agent = build_graph()
    return _agent


# ── models ────────────────────────────────────────────────────────────────────


class BudgetPayload(BaseModel):
    trip_id: str
    action: str
    total_budget: float | None = None
    category: str | None = None
    amount: float | None = None
    description: str | None = None


class PlanRequest(BaseModel):
    message: str
    session_id: str | None = None


class PlanResponse(BaseModel):
    session_id: str
    status: str
    destination: str | None = None
    itinerary: dict[str, Any] | None = None  # ← new Week 5
    flights: list[dict[str, Any]] = []
    hotels: list[dict[str, Any]] = []
    attractions: list[dict[str, Any]] = []
    restaurants: list[dict[str, Any]] = []
    weather: list[dict[str, Any]] = []
    budget: dict[str, Any] = {}
    errors: dict[str, str] = {}
    message: str = ""


# ── existing endpoints (unchanged) ────────────────────────────────────────────


@app.get("/")
def root() -> dict[str, Any]:
    return {"message": "AI Travel Agent", "version": app.version}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok" if cache.is_healthy() else "degraded"}


@app.get("/cache/health")
def cache_health() -> dict[str, Any]:
    return {"healthy": cache.is_healthy()}


@app.get("/flights")
def search_flights(
    origin: str = Query("AMD", min_length=3, max_length=3),
    destination: str = Query("DEL", min_length=3, max_length=3),
) -> dict[str, Any]:
    result = flight_tool._run(origin=origin, destination=destination)
    return {"origin": origin, "destination": destination, "results": result}


@app.post("/api/trip/budget")
def update_budget(payload: BudgetPayload) -> dict[str, Any]:
    return _budget_tool._run(**payload.model_dump())


@app.get("/api/trip/budget/{trip_id}")
def get_budget_summary(trip_id: str) -> dict[str, Any]:
    return _budget_tool._run(trip_id=trip_id, action="get_summary")


@app.get("/api/trip/weather")
def get_weather(city: str, days: int = 7) -> list[dict[str, Any]]:
    return _weather_tool._run(city=city, days=days)


@app.get("/api/hotels")
def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    max_price_per_night: float | None = None,
    min_rating: float | None = None,
    hotel_class: str | None = None,
) -> dict[str, Any]:
    result = hotel_tool._run(
        city=city,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        max_price_per_night=max_price_per_night,
        min_rating=min_rating,
        hotel_class=hotel_class,
    )
    return {
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "adults": adults,
        "count": len(result),
        "results": result,
    }


@app.get("/api/trip/attractions")
def get_attractions(
    city: str, country: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    try:
        return _attraction_tool._run(city=city, country=country, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/trip/restaurants")
def get_restaurants(
    city: str,
    cuisine: str | None = None,
    budget: str | None = None,
    min_rating: float = 0.0,
    limit: int = 10,
) -> list[dict[str, Any]]:
    try:
        return _restaurant_tool._run(
            city=city,
            cuisine=cuisine,
            budget=budget,
            min_rating=min_rating,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── agent endpoint (updated for Week 5) ──────────────────────────────────────


@app.post("/api/plan", response_model=PlanResponse)
def plan_trip(req: PlanRequest) -> PlanResponse:
    """
    POST /api/plan
    {"message": "Paris 5 days $3000", "session_id": "optional"}

    Returns a full PlanResponse including day-by-day itinerary.
    """
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:8]}"
    try:
        graph = _get_agent()
        final_state = graph.invoke(
            {
                "raw_input": req.message,
                "status": "parse",
                "messages": [{"role": "user", "content": req.message}],
            },
            config={"configurable": {"thread_id": session_id}},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent failed: {exc}") from exc

    output: dict[str, Any] = final_state.get("final_output") or {}
    messages = final_state.get("messages") or []
    last_msg = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "assistant"),
        "Trip planning complete.",
    )
    return PlanResponse(
        session_id=session_id,
        status=final_state.get("status", "done"),
        destination=output.get("destination"),
        itinerary=output.get("itinerary"),  # ← new Week 5
        flights=output.get("flights", []),
        hotels=output.get("hotels", []),
        attractions=output.get("attractions", []),
        restaurants=output.get("restaurants", []),
        weather=output.get("weather", []),
        budget=output.get("budget", {}),
        errors=output.get("errors", {}),
        message=last_msg,
    )


# ── NEW: itinerary-only endpoint ──────────────────────────────────────────────


@app.post("/api/itinerary")
def build_itinerary_direct(
    preferences: dict[str, Any],
    flights: list[dict[str, Any]] | None = None,
    hotels: list[dict[str, Any]] | None = None,
    attractions: list[dict[str, Any]] | None = None,
    restaurants: list[dict[str, Any]] | None = None,
    weather: list[dict[str, Any]] | None = None,
    budget_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Call ItineraryBuilderTool directly without the full agent.
    Useful for testing / frontend development.
    """
    from ai_travel_agent.tools.itinerary_builder import ItineraryBuilderTool

    tool = ItineraryBuilderTool()
    try:
        return tool._run(
            preferences=preferences,
            flights=flights or [],
            hotels=hotels or [],
            attractions=attractions or [],
            restaurants=restaurants or [],
            weather=weather or [],
            budget_summary=budget_summary or {},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
