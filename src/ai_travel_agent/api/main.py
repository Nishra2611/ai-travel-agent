"""
src/api/main.py

Start the server:
    poetry run uvicorn src.api.main:app --reload --port 8000

Endpoints this week:
    GET  /health
    GET  /api/flights
    GET  /api/hotels
    GET  /api/cache/status
"""

# from ai_travel_agent.tools.flight_search import FlightSearchTool
# from ai_travel_agent.tools.hotel_search import HotelSearchTool
# from ai_travel_agent.utils.cache import cache
# from fastapi import FastAPI, HTTPException, Query
# from fastapi.middleware.cors import CORSMiddleware

from ai_travel_agent.tools.flight_search import FlightSearchTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.utils.cache import cache
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Travel Agent API",
    description="Epiphyse — Week 2 core search tools",
    version="0.2.0",
)

# Allow the React dev server on port 5173 to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_flight_tool = FlightSearchTool(use_mock_on_failure=True)
_hotel_tool = HotelSearchTool(use_mock_on_failure=True)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "redis": cache.is_healthy()}


# ------------------------------------------------------------------
# Flights
# ------------------------------------------------------------------


@app.get("/api/flights")
def search_flights(
    origin: str = Query(..., description="IATA code e.g. BOM"),
    destination: str = Query(..., description="IATA code e.g. CDG"),
    departure_date: str = Query(..., description="YYYY-MM-DD"),
    return_date: str | None = Query(None),
    adults: int = Query(1, ge=1, le=9),
    max_price: float | None = Query(None),
    max_stops: int | None = Query(None),
    travel_class: int = Query(1, ge=1, le=4),
) -> dict:
    try:
        results = _flight_tool.invoke(
            {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "adults": adults,
                "max_price": max_price,
                "max_stops": max_stops,
                "travel_class": travel_class,
            }
        )
        return {"flights": results, "count": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Hotels
# ------------------------------------------------------------------


@app.get("/api/hotels")
def search_hotels(
    city: str = Query(..., description="City name e.g. Paris"),
    check_in: str = Query(..., description="YYYY-MM-DD"),
    check_out: str = Query(..., description="YYYY-MM-DD"),
    adults: int = Query(2, ge=1, le=9),
    max_price_per_night: float | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=5),
    hotel_class: str | None = Query(None, description="e.g. '4,5'"),
) -> dict:
    try:
        results = _hotel_tool.invoke(
            {
                "city": city,
                "check_in": check_in,
                "check_out": check_out,
                "adults": adults,
                "max_price_per_night": max_price_per_night,
                "min_rating": min_rating,
                "hotel_class": hotel_class,
            }
        )
        return {"hotels": results, "count": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Cache status
# ------------------------------------------------------------------


@app.get("/api/cache/status")
def cache_status() -> dict:
    serpapi_calls = cache.get_api_calls_today("serpapi")
    return {
        "redis_healthy": cache.is_healthy(),
        "serpapi_calls_today": serpapi_calls,
        "daily_limit": 8,
        "remaining": max(0, 8 - serpapi_calls),
    }
