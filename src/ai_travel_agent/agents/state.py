"""
ai_travel_agent/agents/state.py

The TravelState TypedDict is the single object that flows through every
LangGraph node. Every node reads from it and writes back a partial update.
LangGraph merges partials automatically — nodes only touch what they own.

Field naming rules:
  - *_results  : raw list[dict] output from a tool
  - *_error    : str error message if that tool failed, else None
  - status     : controls which node runs next (supervisor reads this)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class TravelState(TypedDict, total=False):
    # ── user input ────────────────────────────────────────────────────
    raw_input: str
    trip_id: str

    # ── parsed preferences (set by preference_parser node) ───────────
    preferences: dict[str, Any]

    # ── tool results ──────────────────────────────────────────────────
    flight_results: list[dict[str, Any]]
    hotel_results: list[dict[str, Any]]
    attraction_results: list[dict[str, Any]]
    restaurant_results: list[dict[str, Any]]
    weather_results: list[dict[str, Any]]
    budget_summary: dict[str, Any]

    # ── per-tool error capture ────────────────────────────────────────
    flight_error: str | None
    hotel_error: str | None
    attraction_error: str | None
    restaurant_error: str | None
    weather_error: str | None
    budget_error: str | None

    # ── conversation memory (LangGraph appends, never replaces) ───────
    messages: Annotated[list[dict[str, str]], operator.add]

    # ── supervisor control flow ───────────────────────────────────────
    # "parse" | "search" | "budget" | "assemble" | "done" | "error"
    status: str

    # ── final assembled output ────────────────────────────────────────
    final_output: dict[str, Any]

    # ── error details ─────────────────────────────────────────────────
    error_message: str | None
