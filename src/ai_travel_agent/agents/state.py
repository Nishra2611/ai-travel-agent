"""
The TravelState TypedDict is the single object that flows through every
LangGraph node. Every node reads from it and writes back a partial update.
LangGraph merges partials automatically — nodes only touch what they own.

Field naming rules:
  - *_results  : raw list[dict] output from a tool
  - *_error    : str error message if that tool failed, else None
  - status     : controls which node runs next (supervisor reads this)

  itinerary_result  : dict output of ItineraryBuilderTool
  itinerary_error   : error string if builder failed

"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from typing_extensions import TypedDict


class TravelState(TypedDict, total=False):
    # ── user input ────────────────────────────────────────────────────
    raw_input: str
    trip_id: str

    # ── parsed preferences ────────────────────────────────────────────
    preferences: dict[str, Any]

    # ── tool results ──────────────────────────────────────────────────
    flight_results: list[dict[str, Any]]
    hotel_results: list[dict[str, Any]]
    attraction_results: list[dict[str, Any]]
    restaurant_results: list[dict[str, Any]]
    weather_results: list[dict[str, Any]]
    budget_summary: dict[str, Any]
    # Week 10 route optimization support
    hotels: list[dict[str, Any]]
    itinerary: dict[str, Any]
    route_optimization: dict[str, Any]  # week 10
    # ── Week 8 budget optimization ────────────────────────────────────
    budget_allocation: dict[str, Any] | None
    budget_tradeoffs: dict[str, Any] | None
    budget_adherence: dict[str, Any] | None
    # -------------week 8--------------------------------------------------
    # ── Week 9 geo clustering ──────────────────────────────────────────
    geo_clusters: dict[str, Any] | None
    # ── Week 9 itinerary builder ───────────────────────────────────────
    itinerary_result: dict[str, Any] | None  # ← new Week 5

    # ── per-tool errors ───────────────────────────────────────────────
    flight_error: str | None
    hotel_error: str | None
    attraction_error: str | None
    restaurant_error: str | None
    weather_error: str | None
    budget_error: str | None
    itinerary_error: str | None  # ← new Week 5

    # ── conversation memory (LangGraph appends) ───────────────────────
    messages: Annotated[list[dict[str, str]], operator.add]

    # ── control flow: parse | search | budget | build | assemble | done | error
    status: str

    # ── final assembled output ────────────────────────────────────────
    final_output: dict[str, Any]

    # ── error details ─────────────────────────────────────────────────
    error_message: str | None
