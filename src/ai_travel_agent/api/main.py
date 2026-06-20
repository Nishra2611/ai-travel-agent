"""FastAPI application entry point."""

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.dummy_tool import DummyFlightTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool
from ai_travel_agent.utils.cache import cache

app = FastAPI(
    title="AI Travel Agent",
    description="Autonomous AI Travel Planning Agent API",
    version="0.1.0",
)

# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Tool instances
# --------------------------------------------------

flight_tool = DummyFlightTool()
hotel_tool = HotelSearchTool()
_weather_tool = WeatherCheckerTool()
_budget_tool = BudgetTrackerTool()

class BudgetPayload(BaseModel):
    trip_id: str
    action: str
    total_budget: float | None = None
    category: str | None = None
    amount: float | None = None
    description: str | None = None
# --------------------------------------------------
# Root
# --------------------------------------------------


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "message": "AI Travel Agent is running",
        "version": app.version,
        "endpoints": [
            "/health",
            "/flights",
            "/api/hotels",
            "/cache/health",
            "/docs",
        ],
    }


# --------------------------------------------------
# Health
# --------------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    healthy = cache.is_healthy()

    return {
        "status": "ok" if healthy else "degraded",
        "cache": "healthy" if healthy else "unavailable",
    }


@app.get("/cache/health")
def cache_health() -> dict[str, Any]:
    healthy = cache.is_healthy()

    return {
        "redis": "connected" if healthy else "using fakeredis (dev mode)",
        "healthy": healthy,
    }


# --------------------------------------------------
# Flights
# --------------------------------------------------


@app.get("/flights")
def search_flights(
    origin: str = Query(default="AMD", min_length=3, max_length=3),
    destination: str = Query(default="DEL", min_length=3, max_length=3),
) -> dict[str, Any]:
    try:
        result = flight_tool._run(
            origin=origin,
            destination=destination,
        )

        return {
            "origin": origin,
            "destination": destination,
            "results": result,
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --------------------------------------------------
# Hotels
# --------------------------------------------------

@app.post("/api/trip/budget")
def update_budget(payload: BudgetPayload):
    try:
        return _budget_tool._run(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"budget error: {exc}",
        ) from exc


@app.get("/api/trip/budget/{trip_id}")
def get_budget_summary(trip_id: str):
    return _budget_tool._run(
        trip_id=trip_id,
        action="get_summary",
    )


@app.get("/api/trip/weather")
def get_weather(city: str, days: int = 7):
    try:
        return _weather_tool._run(city=city, days=days)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"weather lookup failed: {exc}"
        ) from exc


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
    try:
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


    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
