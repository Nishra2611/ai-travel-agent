"""
LangGraph agent graph — Week 11 unified pipeline.

Nodes: parse → fetch_attractions → fetch_weather → build_itinerary → done
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, TypedDict

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from ai_travel_agent.optimizer.itinerary_builder import build_itinerary
from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool

logger = logging.getLogger(__name__)

_attraction_tool = AttractionFinderTool()
_weather_tool = WeatherCheckerTool()


class AgentState(TypedDict, total=False):
    raw_input: str
    status: str
    preferences: dict[str, Any]
    attractions: list[dict[str, Any]]
    weather: list[dict[str, Any]]
    final_output: dict[str, Any]
    messages: list[Any]
    error: str


def _parse_preferences(raw_input: str) -> dict[str, Any]:
    """Extract structured preferences from natural language."""
    text = raw_input.lower()

    # Duration
    duration = 5
    m = re.search(r"(\d+)\s*day", text)
    if m:
        duration = int(m.group(1))

    # Budget
    budget = None
    m = re.search(r"\$\s*(\d[\d,]*)", text)
    if m:
        budget = float(m.group(1).replace(",", ""))

    # Travelers
    travelers = 1
    m = re.search(r"(\d+)\s*(people|person|traveler|pax|adult)", text)
    if m:
        travelers = int(m.group(1))
    elif "couple" in text or "two" in text or " 2 " in text:
        travelers = 2
    elif "family" in text:
        travelers = 4

    # Destination — take the first capitalized word(s) from original input
    dest_match = re.search(r"^([A-Z][a-zA-Z\s]+?)(?:\s+\d|\s+for|\s+trip|,|$)", raw_input)
    destination = dest_match.group(1).strip() if dest_match else "Paris"

    start_date = date.today() + timedelta(days=14)

    return {
        "destination": destination,
        "duration_days": duration,
        "budget_usd": budget,
        "num_travelers": travelers,
        "start_date": start_date.isoformat(),
        "raw_input": raw_input,
    }


def node_parse(state: AgentState) -> AgentState:
    raw = state.get("raw_input", "")
    try:
        prefs = _parse_preferences(raw)
        return {**state, "preferences": prefs, "status": "fetch_attractions"}
    except Exception as exc:
        return {**state, "error": str(exc), "status": "error"}


def node_fetch_attractions(state: AgentState) -> AgentState:
    prefs = state.get("preferences", {})
    destination = prefs.get("destination", "Paris")
    try:
        attractions = _attraction_tool._run(city=destination, limit=20)
        return {**state, "attractions": attractions, "status": "fetch_weather"}
    except Exception as exc:
        logger.warning("Attraction fetch failed: %s", exc)
        return {**state, "attractions": [], "status": "fetch_weather"}


def node_fetch_weather(state: AgentState) -> AgentState:
    prefs = state.get("preferences", {})
    destination = prefs.get("destination", "Paris")
    duration = int(prefs.get("duration_days", 5))
    try:
        weather = _weather_tool._run(city=destination, days=min(duration, 7))
        return {**state, "weather": weather, "status": "build_itinerary"}
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)
        return {**state, "weather": [], "status": "build_itinerary"}


def node_build_itinerary(state: AgentState) -> AgentState:
    prefs = state.get("preferences", {})
    attractions = state.get("attractions", [])
    weather = state.get("weather", [])
    try:
        itinerary = build_itinerary(prefs, attractions, weather)
        return {
            **state,
            "final_output": {"itinerary": itinerary.model_dump()},
            "status": "done",
        }
    except Exception as exc:
        logger.exception("build_itinerary failed: %s", exc)
        return {**state, "error": str(exc), "status": "error"}


def _route(state: AgentState) -> str:
    return state.get("status", "error")


def build_graph(db_path: str = "data/checkpoints.db"):
    builder = StateGraph(AgentState)
    builder.add_node("parse", node_parse)
    builder.add_node("fetch_attractions", node_fetch_attractions)
    builder.add_node("fetch_weather", node_fetch_weather)
    builder.add_node("build_itinerary", node_build_itinerary)

    builder.set_entry_point("parse")
    builder.add_conditional_edges("parse", _route, {
        "fetch_attractions": "fetch_attractions",
        "error": END,
    })
    builder.add_conditional_edges("fetch_attractions", _route, {
        "fetch_weather": "fetch_weather",
        "error": END,
    })
    builder.add_conditional_edges("fetch_weather", _route, {
        "build_itinerary": "build_itinerary",
        "error": END,
    })
    builder.add_conditional_edges("build_itinerary", _route, {
        "done": END,
        "error": END,
    })

    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)
    return builder.compile(checkpointer=memory)
