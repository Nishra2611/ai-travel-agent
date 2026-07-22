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

# week 13
import os
import traceback
import uuid
from pathlib import Path
from typing import Any, cast

from ai_travel_agent.agents.state import TravelState

# week 8 added
from ai_travel_agent.budget.budget_optimizer import (
    BudgetCategory,
    BudgetProfile,
    _BudgetOptimizer,
)

# week 10
from ai_travel_agent.geo.distance_matrix_client import (
    GeoPoint,
    get_distance_matrix_safe,
)

# till here week 8
# week 9
# from ai_travel_agent.geo.distance_matrix_client import GeoPoint
from ai_travel_agent.geo.geo_clustering import _GeoClusterBuilder
from ai_travel_agent.maps.thumbnail_renderer import render_thumbnail_safe

# -- add to your existing nodes.py imports --
from ai_travel_agent.maps.travel_map_generator import (
    MapActivity,
    MapHotel,
    build_travel_map,
)
from ai_travel_agent.pdf.pdf_generator import PDFGenerationError, _PDFGenerator
from ai_travel_agent.pdf.qr_code_generator import generate_qr_code_safe
from ai_travel_agent.pdf.templates import (
    BudgetRow,
    DayActivity,
    DayPlan,
    PDFContext,
)
from ai_travel_agent.pdf.unsplash_client import get_destination_photo_safe
from ai_travel_agent.route.route_optimizer import (
    _RouteOptimizer,
    build_distance_lookup,
)

# till here week 9
from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.flight_search import FlightSearchTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.tools.itinerary_builder import ItineraryBuilderTool
from ai_travel_agent.tools.restaurant_finder import RestaurantFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

MAP_OUTPUT_DIR = "outputs/maps"
# till here week 13

logger = get_logger(__name__)
MIN_ACTIVITIES_TO_OPTIMIZE = 2


_pdf_generator = _PDFGenerator()

PDF_OUTPUT_DIR = "outputs/pdf"
PDF_ASSETS_DIR = "outputs/pdf/assets"


# ── singletons ────────────────────────────────────────────────────────────────
_flight_tool = FlightSearchTool()
_hotel_tool = HotelSearchTool()
_attraction_tool = AttractionFinderTool()
_restaurant_tool = RestaurantFinderTool()
_weather_tool = WeatherCheckerTool()
_budget_tool = BudgetTrackerTool()
_itinerary_tool = ItineraryBuilderTool()  # ← new Week 5
_optimizer = _BudgetOptimizer()  # added in week 8
_cluster_builder = _GeoClusterBuilder()  # added in week 9
_route_optimizer = _RouteOptimizer()  # week 10


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


# ── Week 11: build_itinerary (unified optimizer) ─────────────────────────────


def build_itinerary(state: TravelState) -> dict[str, Any]:
    """
    Week 11 — calls the unified multi-constraint optimizer.
    Replaces the old ItineraryBuilderTool with optimizer/itinerary_builder.py
    which adds geo-clustering, priority scheduling, backtracking, and
    cross-day balance on top of the existing pipeline data.
    """
    from ai_travel_agent.optimizer.itinerary_builder import build_itinerary as _build

    prefs = _prefs(state)
    attractions = state.get("attraction_results") or []
    weather = state.get("weather_results") or []

    logger.info(
        "build_itinerary (Week 11 optimizer): destination=%s days=%s attractions=%d",
        prefs.get("destination"),
        prefs.get("duration_days"),
        len(attractions),
    )

    try:
        itinerary = _build(prefs, attractions, weather)
        result = itinerary.model_dump()
    except Exception as exc:
        logger.error("optimizer/itinerary_builder failed: %s", exc)
        return {
            "itinerary_result": None,
            "itinerary_error": str(exc),
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


# week 9
def build_geo_clusters(state: TravelState) -> dict[str, Any]:
    # attractions = list(state.get("attraction_results") or [])
    # restaurants = list(state.get("restaurant_results") or [])
    # hotels = list(state.get("hotel_results") or [])

    # attractions = cast(
    #     list[dict[str, Any]],
    #     state.get("attraction_results") or [],
    # )

    # restaurants = cast(
    #     list[dict[str, Any]],
    #     state.get("restaurant_results") or [],
    # )

    # hotels = cast(
    #     list[dict[str, Any]],
    #     state.get("hotel_results") or [],
    # )

    # attractions = state.get("attraction_results") or state.get("attractions") or []

    # restaurants = state.get("restaurant_results") or state.get("restaurants") or []

    # hotels = state.get("hotel_results") or state.get("hotels") or []

    attractions_dbg = state.get("attraction_results") or []
    restaurants_dbg = state.get("restaurant_results") or []
    hotels_dbg = state.get("hotel_results") or []

    logger.warning(
        "attraction_results=%s restaurant_results=%s hotel_results=%s",
        len(list(attractions_dbg)),
        len(list(restaurants_dbg)),
        len(list(hotels_dbg)),
    )
    """
    Reads attractions/restaurants/hotels out of state, converts them to
    GeoPoint (skipping any missing lat/lng rather than failing the whole
    node), clusters them, and writes state["geo_clusters"].

    Degrades gracefully: fewer than 3 geocoded points just returns a
    single implicit cluster (see _GeoClusterBuilder.cluster), and this node
    never raises -- a clustering failure shouldn't block build_itinerary or
    assemble_output from running with whatever else succeeded.
    """
    # city = state.get("preferences", {}).get("destination_city", "unknown")
    prefs = _prefs(state)

    city = prefs.get(
        "destination_city",
        prefs.get("destination", "unknown"),
    )
    points = _collect_points(state)

    if not points:
        logger.warning("no geocoded points available, skipping clustering")
        return {"geo_clusters": None}

    try:
        result = _cluster_builder.cluster(city, points)
        logger.info(
            "geo clusters built",
            extra={
                "city": city,
                "num_points": len(points),
                "num_clusters": len(result.clusters),
            },
        )
        return {"geo_clusters": result.as_dict()}
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- clustering failure must not break the graph
        logger.error("geo clustering failed", extra={"error": str(exc)})
        return {"geo_clusters": None}


def _collect_points(state: TravelState) -> list[GeoPoint]:
    points: list[GeoPoint] = []

    attractions = cast(
        list[dict[str, Any]],
        state.get("attraction_results") or state.get("attractions") or [],
    )
    for attraction in attractions:

        # for attraction in state.get("attractions") or []:
        if (
            attraction.get("latitude") is not None
            and attraction.get("longitude") is not None
        ):
            points.append(
                GeoPoint(
                    id=attraction.get("id", attraction.get("name", "")),
                    name=attraction.get("name", "unknown attraction"),
                    latitude=attraction["latitude"],
                    longitude=attraction["longitude"],
                )
            )

    restaurants = cast(
        list[dict[str, Any]],
        state.get("restaurant_results") or state.get("restaurants") or [],
    )

    for restaurant in restaurants:

        # for restaurant in state.get("restaurants") or []:
        if (
            restaurant.get("latitude") is not None
            and restaurant.get("longitude") is not None
        ):
            points.append(
                GeoPoint(
                    id=restaurant.get("id", restaurant.get("name", "")),
                    name=restaurant.get("name", "unknown restaurant"),
                    latitude=restaurant["latitude"],
                    longitude=restaurant["longitude"],
                )
            )

    hotels = state.get("hotel_results") or state.get("hotels") or []

    if (
        hotels
        and hotels[0].get("latitude") is not None
        and hotels[0].get("longitude") is not None
    ):
        points.append(
            GeoPoint(
                id=hotels[0].get("id", "hotel"),
                name=hotels[0].get("name", "hotel"),
                latitude=hotels[0]["latitude"],
                longitude=hotels[0]["longitude"],
            )
        )

    return points


# week 9


# week 10
def optimize_routes(state: TravelState) -> dict[str, Any]:
    """
    For each day in state["itinerary"]["days"]: builds a GeoPoint list from
    the day's activities + the trip hotel, fetches a per-day distance
    matrix, runs _RouteOptimizer, and reorders that day's activities list
    in place to the optimized order. Writes state["route_optimization"]
    with per-day efficiency_score/improvement_pct for assemble_output to
    surface.

    Never raises: a day that can't be optimized (missing coordinates, <2
    activities, distance matrix failure) is left in its original order and
    recorded with efficiency_score=None rather than blocking the other
    days or the rest of the graph.
    """
    itinerary = state.get("itinerary_result") or state.get("itinerary")
    hotel_point = _extract_hotel_point(state)

    if not itinerary or not itinerary.get("days") or hotel_point is None:
        logger.warning(
            "no itinerary or hotel coordinates available, skipping route optimization"
        )
        return {"route_optimization": None}

    per_day_results: dict[str, dict[str, Any]] = {}
    for day_index, day in enumerate(itinerary["days"]):
        day_key = f"day_{day_index + 1}"
        activity_points, activities_by_id = _extract_activity_points(day)

        if len(activity_points) < MIN_ACTIVITIES_TO_OPTIMIZE:
            per_day_results[day_key] = {
                "skipped": True,
                "reason": "fewer than 2 geocoded activities",
            }
            continue

        try:
            matrix = get_distance_matrix_safe(
                [hotel_point, *activity_points], profile="walking"
            )
            distance_lookup = build_distance_lookup(matrix)
            result = _route_optimizer.optimize_day(
                hotel_point, activity_points, distance_lookup, seed=day_index
            )

            day["activities"] = [
                activities_by_id[p.id] for p in result.ordered_activities
            ]
            per_day_results[day_key] = result.as_dict()
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"route optimization failed for day {day_key}: {exc}")
            per_day_results[day_key] = {"skipped": True, "reason": str(exc)}

    logger.info("route optimization complete", extra={"num_days": len(per_day_results)})
    return {
        "itinerary": itinerary,
        "itinerary_result": itinerary,
        "route_optimization": per_day_results,
    }


# def _extract_hotel_point(state: TravelState) -> GeoPoint | None:
#     hotels = state.get("hotels") or []
def _extract_hotel_point(state: TravelState) -> GeoPoint | None:
    hotels = state.get("hotel_results") or state.get("hotels") or []
    if not hotels:
        return None
    hotel = hotels[0]
    if hotel.get("latitude") is None or hotel.get("longitude") is None:
        return None
    return GeoPoint(
        id=hotel.get("id", "hotel"),
        name=hotel.get("name", "hotel"),
        latitude=hotel["latitude"],
        longitude=hotel["longitude"],
    )


def _extract_activity_points(
    day: dict[str, Any]
) -> tuple[list[GeoPoint], dict[str, dict[str, Any]]]:
    """
    Returns (geocoded points for this day, id -> original activity dict)
    so the optimized order can be mapped straight back onto the itinerary's
    activity dicts without losing any fields the itinerary builder set
    (cost, category, time slot, etc).
    """
    points: list[GeoPoint] = []
    by_id: dict[str, dict[str, Any]] = {}
    for i, activity in enumerate(day.get("activities", [])):
        if activity.get("latitude") is None or activity.get("longitude") is None:
            continue
        activity_id = activity.get("id") or activity.get("name") or f"activity_{i}"
        point = GeoPoint(
            id=activity_id,
            name=activity.get("name", activity_id),
            latitude=activity["latitude"],
            longitude=activity["longitude"],
        )
        points.append(point)
        by_id[activity_id] = activity
    return points, by_id


# week 10


# week 13
def generate_map(state: TravelState) -> dict:
    """
    Builds the interactive HTML map from the final itinerary + hotel, then
    rasterizes a PNG thumbnail for the Week 14 PDF to embed. Runs after
    assemble_output (needs the finished itinerary, not an intermediate
    one) and never raises -- a mapping failure shouldn't cost the person
    their itinerary JSON/PDF.
    """
    hotel_dict = (state.get("hotels") or [None])[0]
    itinerary = state.get("itinerary")

    if not hotel_dict or not itinerary or not itinerary.get("days"):
        logger.warning("no hotel/itinerary available, skipping map generation")
        return {"map_output": None}

    if hotel_dict.get("latitude") is None or hotel_dict.get("longitude") is None:
        logger.warning("hotel missing coordinates, skipping map generation")
        return {"map_output": None}

    hotel = MapHotel(
        id=hotel_dict.get("id", "hotel"),
        name=hotel_dict.get("name", "Hotel"),
        latitude=hotel_dict["latitude"],
        longitude=hotel_dict["longitude"],
    )
    days = [_to_map_activities(day) for day in itinerary["days"]]

    try:
        # html_path = os.path.join(MAP_OUTPUT_DIR, "travel_map.html")
        # thumbnail_path = os.path.join(MAP_OUTPUT_DIR, "travel_map_thumbnail.png")
        html_path = Path(MAP_OUTPUT_DIR, "travel_map.html").as_posix()
        thumbnail_path = Path(MAP_OUTPUT_DIR, "travel_map_thumbnail.png").as_posix()

        build_travel_map(hotel, days, html_path, animate=True)
        actual_thumbnail = render_thumbnail_safe(html_path, thumbnail_path)

        logger.info(
            "map generated",
            extra={
                "html_path": html_path,
                "has_thumbnail": actual_thumbnail is not None,
            },
        )
        return {
            "map_output": {
                "html_path": html_path,
                "thumbnail_path": str(actual_thumbnail) if actual_thumbnail else None,
            }
        }
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- the map is a bonus artifact, not a required one
        logger.error("map generation failed", extra={"error": str(exc)})
        return {"map_output": None}


def _to_map_activities(day: dict) -> list[MapActivity]:
    activities = []
    for i, activity in enumerate(day.get("activities", [])):
        if activity.get("latitude") is None or activity.get("longitude") is None:
            continue
        activities.append(
            MapActivity(
                id=activity.get("id") or activity.get("name") or f"activity_{i}",
                name=activity.get("name", "Activity"),
                latitude=activity["latitude"],
                longitude=activity["longitude"],
                time_slot=activity.get("time_slot"),
                cost=activity.get("cost"),
                category=activity.get("category"),
            )
        )
    return activities


# week 13


# week 14
def generate_pdf(state: TravelState) -> dict:
    """
    Builds the PDFContext from state and renders the final PDF itinerary.
    Never raises: a PDF failure (WeasyPrint missing/system libs, malformed
    data) is recorded in state["pdf_output"]["status"] rather than taking
    down a run where the JSON itinerary and the HTML map both already
    succeeded.
    """
    itinerary = state.get("itinerary")
    if not itinerary or not itinerary.get("days"):
        logger.warning("no itinerary available, skipping PDF generation")
        return {"pdf_output": None}

    try:
        context = _build_pdf_context(state)
        output_path = os.path.join(PDF_OUTPUT_DIR, "itinerary.pdf")
        _pdf_generator.build(context, output_path)
        return {
            "pdf_output": {
                "pdf_path": str(output_path).replace("\\", "/"),
                "status": "generated",
                "error": None,
            }
        }
    except PDFGenerationError as exc:
        logger.error("PDF generation failed", extra={"error": str(exc)})
        return {"pdf_output": {"pdf_path": None, "status": "failed", "error": str(exc)}}
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- context-building bugs shouldn't crash the graph either
        logger.error("PDF context assembly failed", extra={"error": str(exc)})
        return {"pdf_output": {"pdf_path": None, "status": "failed", "error": str(exc)}}


def _build_pdf_context(state: TravelState) -> PDFContext:
    prefs = state.get("preferences", {})
    destination = prefs.get("destination_city", "Your Trip")
    itinerary = state["itinerary"]

    days = [
        DayPlan(
            day_number=i + 1,
            activities=[
                DayActivity(
                    name=a.get("name", "Activity"),
                    time_slot=a.get("time_slot"),
                    cost=a.get("cost"),
                )
                for a in day.get("activities", [])
            ],
        )
        for i, day in enumerate(itinerary["days"])
    ]

    allocation = state.get("budget_allocation") or {}
    actual_spend = _extract_actual_spend(state)
    budget_rows = [
        BudgetRow(
            category=category.value.title(),
            allocated=(
                allocation.get("allocations", {}).get(category.value, {}) or {}
            ).get("amount", 0.0),
            spent=actual_spend.get(category, 0.0),
        )
        for category in BudgetCategory
    ]
    total_budget = allocation.get("total_budget", 0.0)
    total_spent = sum(actual_spend.values())
    adherence = state.get("budget_adherence") or {}

    cover_photo_path = get_destination_photo_safe(
        f"{destination} skyline", os.path.join(PDF_ASSETS_DIR, "cover.jpg")
    )

    map_output = state.get("map_output") or {}
    qr_code_path = None
    if map_output.get("html_path"):
        qr_target = _resolve_map_share_url(map_output["html_path"])
        qr_code_path = generate_qr_code_safe(
            qr_target, os.path.join(PDF_ASSETS_DIR, "map_qr.png")
        )

    return PDFContext(
        destination=destination,
        trip_dates=prefs.get("trip_dates", "Dates TBD"),
        executive_summary=_build_executive_summary(
            destination, len(days), allocation, adherence
        ),
        days=days,
        budget_rows=budget_rows,
        total_budget=total_budget,
        total_spent=total_spent,
        budget_verdict=adherence.get("verdict"),
        cover_photo_path=str(cover_photo_path) if cover_photo_path else None,
        map_thumbnail_path=map_output.get("thumbnail_path"),
        qr_code_path=str(qr_code_path) if qr_code_path else None,
    )


def _build_executive_summary(
    destination: str, num_days: int, allocation: dict, adherence: dict
) -> str:
    profile = allocation.get("profile", "trip")
    summary = f"A {num_days}-day {profile.replace('_', '-')} trip to {destination}."
    if adherence.get("overall_score") is not None:
        summary += f" Budget adherence score: {adherence['overall_score']}/100 ({adherence.get('verdict', 'n/a').replace('_', ' ')})."
    return summary


def _resolve_map_share_url(html_path: str) -> str:
    """See qr_code_generator.py's module docstring: a bare file:// path
    won't open on most phone QR scanners. If PUBLIC_MAP_BASE_URL is set
    (e.g. once a hosting/sharing endpoint exists), use that; otherwise
    fall back to the local file URI and log that it's demo-only."""
    base_url = os.environ.get("PUBLIC_MAP_BASE_URL")
    if base_url:
        return f"{base_url.rstrip('/')}/{os.path.basename(html_path)}"
    logger.warning(
        "PUBLIC_MAP_BASE_URL not set, QR code will encode a local file path "
        "that most phone scanners can't open -- fine for a live demo on the "
        "same machine, not for sharing"
    )
    return f"file://{os.path.abspath(html_path)}"


# week 14
