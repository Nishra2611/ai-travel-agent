"""

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

build_itinerary
  - Calls ItineraryBuilderTool with all collected results
  - Writes itinerary_result to state
  - assemble_output is updated to include the itinerary in final_output

"""

from __future__ import annotations

import traceback
import uuid
from typing import Any

from ai_travel_agent.agents.state import TravelState

# week 8 added
from ai_travel_agent.budget.budget_optimizer import (
    BudgetCategory,
    BudgetProfile,
    _BudgetOptimizer,
)

# till here week 8
from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.flight_search import FlightSearchTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.tools.itinerary_builder import ItineraryBuilderTool
from ai_travel_agent.tools.restaurant_finder import RestaurantFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

# ── singletons ────────────────────────────────────────────────────────────────
_flight_tool = FlightSearchTool()
_hotel_tool = HotelSearchTool()
_attraction_tool = AttractionFinderTool()
_restaurant_tool = RestaurantFinderTool()
_weather_tool = WeatherCheckerTool()
_budget_tool = BudgetTrackerTool()
_itinerary_tool = ItineraryBuilderTool()  # ← new Week 5
_optimizer = _BudgetOptimizer()  # added in week 8


def _safe_run(tool_name: str, fn: Any, **kwargs: Any) -> tuple[Any, str | None]:
    try:
        return fn(**kwargs), None
    except Exception as exc:
        msg = f"{tool_name} failed: {exc}"
        logger.error("%s\n%s", msg, traceback.format_exc())
        return None, msg


def _prefs(state: TravelState) -> dict[str, Any]:
    return state.get("preferences") or {}


# ── existing nodes (unchanged from Week 4) ────────────────────────────────────


def parse_preferences(state: TravelState) -> dict[str, Any]:
    from ai_travel_agent.parsers.preference_parser import PreferenceParserTool

    raw = state.get("raw_input", "")
    tool = PreferenceParserTool()
    result, err = _safe_run("PreferenceParser", tool._run, user_input=raw)
    if err or result is None:
        return {
            "status": "error",
            "error_message": err or "PreferenceParser returned nothing",
            "messages": [{"role": "system", "content": f"Parse failed: {err}"}],
        }
    trip_id = state.get("trip_id") or f"trip_{uuid.uuid4().hex[:8]}"
    return {
        "preferences": result,
        "trip_id": trip_id,
        "status": "search",
        "messages": [
            {
                "role": "assistant",
                "content": f"Planning a trip to {result.get('destination', '?')} "
                f"for {result.get('duration_days', '?')} days.",
            }
        ],
    }


# week 8
def allocate_budget(state: TravelState) -> dict[str, Any]:
    prefs: dict[str, Any] = state.get("preferences", {})
    # prefs = state.get("preferences", {})

    total_budget = prefs.get("total_budget") or prefs.get("budget_usd")

    profile = prefs.get(
        "budget_profile",
        BudgetProfile.MID_RANGE.value,
    )

    preference_text = prefs.get("raw_preference_text") or state.get("raw_input")

    if not total_budget:
        logger.warning("No budget supplied")
        return {"budget_allocation": None}

    try:
        allocation = _optimizer.allocate(
            total_budget=float(total_budget),
            profile=profile,
            preference_text=preference_text,
        )

        return {"budget_allocation": allocation.as_dict()}

    except Exception as exc:
        logger.error("Budget allocation failed: %s", exc)

        return {
            "budget_allocation": None,
            "budget_error": str(exc),
        }


# week 8


def search_flights(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    result, err = _safe_run(
        "FlightSearch",
        _flight_tool._run,
        origin=prefs.get("origin") or "BOM",
        destination=prefs.get("destination", ""),
        departure_date=str(prefs.get("start_date") or "2025-12-10"),
        adults=prefs.get("num_travelers", 1),
    )
    if err or not result:
        return {"flight_results": [], "flight_error": err or "no results"}
    return {"flight_results": result, "flight_error": None}


def search_hotels(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    result, err = _safe_run(
        "HotelSearch",
        _hotel_tool._run,
        city=prefs.get("destination", ""),
        check_in=str(prefs.get("start_date") or "2025-12-10"),
        check_out=str(prefs.get("end_date") or "2025-12-15"),
        adults=prefs.get("num_travelers", 2),
    )
    if err or not result:
        return {"hotel_results": [], "hotel_error": err or "no results"}
    return {"hotel_results": result, "hotel_error": None}


def find_attractions(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    result, err = _safe_run(
        "AttractionFinder",
        _attraction_tool._run,
        city=prefs.get("destination", ""),
        limit=15,
    )
    if err or not result:
        return {"attraction_results": [], "attraction_error": err or "no results"}
    return {"attraction_results": result, "attraction_error": None}


def find_restaurants(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    dietary = prefs.get("dietary_restrictions") or []
    result, err = _safe_run(
        "RestaurantFinder",
        _restaurant_tool._run,
        city=prefs.get("destination", ""),
        cuisine=dietary[0] if dietary else None,
        limit=10,
    )
    if err or not result:
        return {"restaurant_results": [], "restaurant_error": err or "no results"}
    return {"restaurant_results": result, "restaurant_error": None}


def check_weather(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    result, err = _safe_run(
        "WeatherChecker",
        _weather_tool._run,
        city=prefs.get("destination", ""),
        days=min(prefs.get("duration_days", 7), 8),
    )
    if err or not result:
        return {"weather_results": [], "weather_error": err or "no results"}
    return {"weather_results": result, "weather_error": None}


def track_budget(state: TravelState) -> dict[str, Any]:
    prefs = _prefs(state)
    trip_id = state.get("trip_id", f"trip_{uuid.uuid4().hex[:8]}")
    total_budget = prefs.get("budget_usd")
    if total_budget:
        _safe_run(
            "BudgetTracker.set",
            _budget_tool._run,
            trip_id=trip_id,
            action="set_budget",
            total_budget=float(total_budget),
        )
    flights = state.get("flight_results") or []
    if flights:
        cheapest = min(flights, key=lambda f: f.get("total_price_usd", 9999))
        _safe_run(
            "BudgetTracker.flight",
            _budget_tool._run,
            trip_id=trip_id,
            action="add_expense",
            category="flights",
            amount=cheapest.get("total_price_usd", 0),
            description="Flight",
        )
    hotels = state.get("hotel_results") or []
    if hotels:
        _safe_run(
            "BudgetTracker.hotel",
            _budget_tool._run,
            trip_id=trip_id,
            action="add_expense",
            category="accommodation",
            amount=hotels[0].get("total_price_usd", 0),
            description=f"Hotel: {hotels[0].get('name', 'unknown')}",
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


# ── NEW Week 5: build_itinerary ───────────────────────────────────────────────


def build_itinerary(state: TravelState) -> dict[str, Any]:
    """
    Week 5 node — assembles all tool results into a structured Itinerary.
    Runs after track_budget, before assemble_output.
    Writes itinerary_result to state.
    """
    prefs = _prefs(state)
    logger.info(
        "build_itinerary: destination=%s days=%s",
        prefs.get("destination"),
        prefs.get("duration_days"),
    )

    result, err = _safe_run(
        "ItineraryBuilder",
        _itinerary_tool._run,
        preferences=prefs,
        flights=state.get("flight_results") or [],
        hotels=state.get("hotel_results") or [],
        attractions=state.get("attraction_results") or [],
        restaurants=state.get("restaurant_results") or [],
        weather=state.get("weather_results") or [],
        budget_summary=state.get("budget_summary") or {},
    )

    if err or result is None:
        logger.error("ItineraryBuilder failed: %s", err)
        return {
            "itinerary_result": None,
            "itinerary_error": err or "builder returned nothing",
        }

    days = result.get("days", [])
    total_acts = sum(len(d.get("activities", [])) for d in days)
    logger.info("build_itinerary: %d days, %d activities", len(days), total_acts)

    return {
        "itinerary_result": result,
        "itinerary_error": None,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"Built a {len(days)}-day itinerary for {prefs.get('destination', '?')} "
                    f"with {total_acts} activities across all days."
                ),
            }
        ],
    }


# ── UPDATED assemble_output — includes itinerary ─────────────────────────────


def assemble_output(state: TravelState) -> dict[str, Any]:
    """
    Updated for Week 5: includes itinerary_result in final_output.
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
            "itinerary": state.get("itinerary_error"),
        }.items()
        if v is not None
    }

    itinerary = state.get("itinerary_result")

    final: dict[str, Any] = {
        "trip_id": state.get("trip_id"),
        "destination": destination,
        "preferences": prefs,
        "itinerary": itinerary,  # ← new in Week 5
        "flights": state.get("flight_results") or [],
        "hotels": state.get("hotel_results") or [],
        "attractions": state.get("attraction_results") or [],
        "restaurants": state.get("restaurant_results") or [],
        "weather": state.get("weather_results") or [],
        "budget": state.get("budget_summary") or {},
        # week 8
        "budget_allocation": state.get("budget_allocation"),
        "budget_tradeoffs": state.get("budget_tradeoffs"),
        "budget_adherence": state.get("budget_adherence"),
        # week 8
        "errors": errors,
        "tools_succeeded": 7 - len(errors),  # 7 tools in Week 5
        "tools_failed": len(errors),
    }

    logger.info(
        "assemble_output: destination=%s succeeded=%d failed=%d",
        destination,
        final["tools_succeeded"],
        final["tools_failed"],
    )

    within_budget = ""
    if itinerary and itinerary.get("budget_usd"):
        within_budget = (
            " Within budget."
            if itinerary.get("is_within_budget", True)
            else " Over budget — consider adjustments."
        )

    return {
        "final_output": final,
        "status": "done",
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"Your {destination} trip plan is ready with a full day-by-day itinerary."
                    f"{within_budget} {final['tools_succeeded']}/7 data sources succeeded."
                ),
            }
        ],
    }


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


# week 8
def evaluate_budget(state: TravelState) -> dict[str, Any]:
    allocation_dict = state.get("budget_allocation")

    if not allocation_dict:
        return {
            "budget_tradeoffs": None,
            "budget_adherence": None,
        }

    actual_spend = _extract_actual_spend(state)

    allocation = _optimizer.allocate(
        total_budget=allocation_dict["total_budget"],
        profile=allocation_dict["profile"],
    )

    tradeoffs = _optimizer.suggest_tradeoffs(
        allocation,
        actual_spend,
    )

    adherence = _optimizer.adherence_score(
        allocation,
        actual_spend,
    )

    return {
        "budget_tradeoffs": tradeoffs.as_dict(),
        "budget_adherence": adherence.as_dict(),
    }


def _extract_actual_spend(
    state: TravelState,
) -> dict[BudgetCategory, float]:

    flights = state.get("flight_results") or []
    hotels = state.get("hotel_results") or []
    itinerary = state.get("itinerary_result") or {}

    flights_cost = 0.0
    if flights:
        flights_cost = flights[0].get(
            "total_price_usd",
            0.0,
        )

    hotel_cost = 0.0
    if hotels:
        hotel_cost = hotels[0].get(
            "total_price_usd",
            0.0,
        )

    activities_cost = 0.0
    food_cost = 0.0

    for day in itinerary.get("days", []):
        for activity in day.get("activities", []):

            if activity.get("category") == "activity":
                activities_cost += activity.get(
                    "cost",
                    0.0,
                )

            if activity.get("category") == "restaurant":
                food_cost += activity.get(
                    "cost",
                    0.0,
                )

    return {
        BudgetCategory.FLIGHTS: flights_cost,
        BudgetCategory.ACCOMMODATION: hotel_cost,
        BudgetCategory.FOOD: food_cost,
        BudgetCategory.ACTIVITIES: activities_cost,
        BudgetCategory.TRANSPORT: 0.0,
        BudgetCategory.MISC: 0.0,
    }


# week 8
