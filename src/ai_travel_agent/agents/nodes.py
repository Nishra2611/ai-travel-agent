"""
ai_travel_agent/agents/nodes.py

One function per LangGraph node. Each receives the full TravelState and
returns a dict of only the fields it changes — LangGraph merges the rest.

Node responsibilities:
  parse_preferences  → runs PreferenceParserTool, writes preferences
  search_flights     → runs FlightSearchTool,     writes flight_results
  search_hotels      → runs HotelSearchTool,      writes hotel_results
  find_attractions   → runs AttractionFinderTool, writes attraction_results
  find_restaurants   → runs RestaurantFinderTool, writes restaurant_results
  check_weather      → runs WeatherCheckerTool,   writes weather_results
  track_budget       → runs BudgetTrackerTool,    writes budget_summary
  assemble_output    → merges all results into final_output
  handle_error       → formats error_message for caller
"""

from __future__ import annotations

import traceback
import uuid
from typing import Any

from ai_travel_agent.agents.state import TravelState
from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.flight_search import FlightSearchTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.tools.restaurant_finder import RestaurantFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

# ── tool singletons (instantiated once, reused across invocations) ────────────

_flight_tool = FlightSearchTool()
_hotel_tool = HotelSearchTool()
_attraction_tool = AttractionFinderTool()
_restaurant_tool = RestaurantFinderTool()
_weather_tool = WeatherCheckerTool()
_budget_tool = BudgetTrackerTool()


# ── helpers ───────────────────────────────────────────────────────────────────


def _safe_run(tool_name: str, fn: Any, **kwargs: Any) -> tuple[Any, str | None]:
    """
    Execute fn(**kwargs) and return (result, error_str).
    Never raises — all exceptions are caught and returned as error strings.
    """
    try:
        return fn(**kwargs), None
    except Exception as exc:
        msg = f"{tool_name} failed: {exc}"
        logger.error("%s\n%s", msg, traceback.format_exc())
        return None, msg


def _prefs(state: TravelState) -> dict[str, Any]:
    """Shortcut — returns preferences dict, empty dict if not yet parsed."""
    return state.get("preferences") or {}


# ── node: parse_preferences ───────────────────────────────────────────────────


def parse_preferences(state: TravelState) -> dict[str, Any]:
    """
    Parse the raw user message into a structured TravelPreferences dict.
    Uses the local Ollama LLM via PreferenceParserTool.
    On failure: sets status="error" so the supervisor short-circuits.
    """
    from ai_travel_agent.parsers.preference_parser import PreferenceParserTool

    raw = state.get("raw_input", "")
    logger.info("parse_preferences: input=%r", raw[:80])

    tool = PreferenceParserTool()
    result, err = _safe_run("PreferenceParser", tool._run, user_input=raw)

    if err or result is None:
        return {
            "status": "error",
            "error_message": err or "PreferenceParser returned nothing",
            "messages": [{"role": "system", "content": f"Parse failed: {err}"}],
        }

    trip_id = state.get("trip_id") or f"trip_{uuid.uuid4().hex[:8]}"
    logger.info("parse_preferences: destination=%s", result.get("destination"))

    return {
        "preferences": result,
        "trip_id": trip_id,
        "status": "search",
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"Got it — planning a trip to {result.get('destination', '?')} "
                    f"for {result.get('duration_days', '?')} days."
                ),
            }
        ],
    }


# ── node: search_flights ──────────────────────────────────────────────────────


def search_flights(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    origin = prefs.get("origin") or "BOM"
    destination = prefs.get("destination", "")
    departure_date = prefs.get("start_date") or "2025-12-10"

    logger.info("search_flights: %s → %s on %s", origin, destination, departure_date)

    result, err = _safe_run(
        "FlightSearch",
        _flight_tool._run,
        origin=origin,
        destination=destination,
        departure_date=str(departure_date),
        adults=prefs.get("num_travelers", 1),
    )

    if err or not result:
        return {"flight_results": [], "flight_error": err or "no results"}

    return {"flight_results": result, "flight_error": None}


# ── node: search_hotels ───────────────────────────────────────────────────────


def search_hotels(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    city = prefs.get("destination", "")
    check_in = str(prefs.get("start_date") or "2025-12-10")
    check_out = str(prefs.get("end_date") or "2025-12-15")

    logger.info("search_hotels: city=%s %s→%s", city, check_in, check_out)

    result, err = _safe_run(
        "HotelSearch",
        _hotel_tool._run,
        city=city,
        check_in=check_in,
        check_out=check_out,
        adults=prefs.get("num_travelers", 2),
    )

    if err or not result:
        return {"hotel_results": [], "hotel_error": err or "no results"}

    return {"hotel_results": result, "hotel_error": None}


# ── node: find_attractions ────────────────────────────────────────────────────


def find_attractions(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    city = prefs.get("destination", "")

    logger.info("find_attractions: city=%s", city)

    result, err = _safe_run(
        "AttractionFinder",
        _attraction_tool._run,
        city=city,
        limit=15,
    )

    if err or not result:
        return {"attraction_results": [], "attraction_error": err or "no results"}

    return {"attraction_results": result, "attraction_error": None}


# ── node: find_restaurants ────────────────────────────────────────────────────


def find_restaurants(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    city = prefs.get("destination", "")
    dietary = prefs.get("dietary_restrictions") or []
    cuisine = dietary[0] if dietary else None

    logger.info("find_restaurants: city=%s cuisine=%s", city, cuisine)

    result, err = _safe_run(
        "RestaurantFinder",
        _restaurant_tool._run,
        city=city,
        cuisine=cuisine,
        limit=10,
    )

    if err or not result:
        return {"restaurant_results": [], "restaurant_error": err or "no results"}

    return {"restaurant_results": result, "restaurant_error": None}


# ── node: check_weather ───────────────────────────────────────────────────────


def check_weather(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    city = prefs.get("destination", "")
    days = min(prefs.get("duration_days", 7), 8)  # OWM max is 8

    logger.info("check_weather: city=%s days=%d", city, days)

    result, err = _safe_run(
        "WeatherChecker",
        _weather_tool._run,
        city=city,
        days=days,
    )

    if err or not result:
        return {"weather_results": [], "weather_error": err or "no results"}

    return {"weather_results": result, "weather_error": None}


# ── node: track_budget ────────────────────────────────────────────────────────


def track_budget(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    trip_id = state.get("trip_id", f"trip_{uuid.uuid4().hex[:8]}")
    total_budget = prefs.get("budget_usd")

    if total_budget:
        logger.info(
            "track_budget: set_budget trip=%s amount=%.2f", trip_id, total_budget
        )
        _safe_run(
            "BudgetTracker.set_budget",
            _budget_tool._run,
            trip_id=trip_id,
            action="set_budget",
            total_budget=float(total_budget),
        )

    # Auto-add flight cost if available
    flights = state.get("flight_results") or []
    if flights:
        cheapest = min(flights, key=lambda f: f.get("total_price_usd", 9999))
        _safe_run(
            "BudgetTracker.add_flight",
            _budget_tool._run,
            trip_id=trip_id,
            action="add_expense",
            category="flights",
            amount=cheapest.get("total_price_usd", 0),
            description="Cheapest flight option",
        )

    # Auto-add hotel cost if available
    hotels = state.get("hotel_results") or []
    if hotels:
        top_hotel = hotels[0]
        _safe_run(
            "BudgetTracker.add_hotel",
            _budget_tool._run,
            trip_id=trip_id,
            action="add_expense",
            category="accommodation",
            amount=top_hotel.get("total_price_usd", 0),
            description=f"Hotel: {top_hotel.get('name', 'unknown')}",
        )

    summary, err = _safe_run(
        "BudgetTracker.summary",
        _budget_tool._run,
        trip_id=trip_id,
        action="get_summary",
    )

    if err or summary is None:
        return {"budget_summary": {}, "budget_error": err or "no summary"}

    return {"budget_summary": summary, "budget_error": None}


# ── node: assemble_output ─────────────────────────────────────────────────────


def assemble_output(state: TravelState) -> dict[str, Any]:
    """
    Gather all tool results into a single structured final_output dict.
    This is what the API caller receives.
    """
    prefs = _prefs(state)
    destination = prefs.get("destination", "Unknown")

    errors = {
        k: v
        for k, v in {
            "flights": state.get("flight_error"),
            "hotels": state.get("hotel_error"),
            "attractions": state.get("attraction_error"),
            "restaurants": state.get("restaurant_error"),
            "weather": state.get("weather_error"),
            "budget": state.get("budget_error"),
        }.items()
        if v is not None
    }

    final: dict[str, Any] = {
        "trip_id": state.get("trip_id"),
        "destination": destination,
        "preferences": prefs,
        "flights": state.get("flight_results") or [],
        "hotels": state.get("hotel_results") or [],
        "attractions": state.get("attraction_results") or [],
        "restaurants": state.get("restaurant_results") or [],
        "weather": state.get("weather_results") or [],
        "budget": state.get("budget_summary") or {},
        "errors": errors,
        "tools_succeeded": 6 - len(errors),
        "tools_failed": len(errors),
    }

    logger.info(
        "assemble_output: destination=%s succeeded=%d failed=%d",
        destination,
        final["tools_succeeded"],
        final["tools_failed"],
    )

    return {
        "final_output": final,
        "status": "done",
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"Your {destination} trip plan is ready. "
                    f"{final['tools_succeeded']}/6 data sources succeeded."
                ),
            }
        ],
    }


# ── node: handle_error ────────────────────────────────────────────────────────


def handle_error(state: TravelState) -> dict[str, Any]:
    msg = state.get("error_message", "Unknown error")
    logger.error("handle_error: %s", msg)
    return {
        "status": "done",
        "final_output": {"error": msg, "success": False},
        "messages": [
            {"role": "assistant", "content": f"Sorry, something went wrong: {msg}"}
        ],
    }
