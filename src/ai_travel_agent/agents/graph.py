"""
Builds and compiles the LangGraph StateGraph.

Graph topology:
  START
    ↓
  [supervisor_router]  ← conditional edge after every tool node
    ↓ "parse"
  parse_preferences
    ↓ (sets status="search")
  [supervisor_router]
    ↓ "search"
  search_flights  ──┐
  search_hotels   ──┤  parallel fan-out
  find_attractions──┤  (LangGraph runs these concurrently)
  find_restaurants──┤
  check_weather   ──┘
    ↓ all complete → status="budget"
  [supervisor_router]
    ↓ "budget"
  track_budget
    ↓ status="assemble"
  assemble_output
    ↓ status="done"
  END

The SQLite checkpointer gives every session a thread_id so conversation
history and tool results persist across multiple HTTP requests.

Usage:
    from ai_travel_agent.agents.graph import build_graph
    graph = build_graph()
    result = graph.invoke(
        {"raw_input": "Paris 5 days $3000", "status": "parse", "messages": []},
        config={"configurable": {"thread_id": "session-abc"}},
    )

New pipeline:
  parse_preferences
    → search_flights → search_hotels → find_attractions
    → find_restaurants → check_weather
    → track_budget
    → build_itinerary     ← NEW Week 5
    → assemble_output
    → END
"""

from __future__ import annotations

import sqlite3
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from ai_travel_agent.agents.nodes import (
    allocate_budget,
    assemble_output,
    build_geo_clusters,
    build_itinerary,
    check_weather,
    evaluate_budget,
    find_attractions,
    find_restaurants,
    handle_error,
    parse_preferences,
    search_flights,
    search_hotels,
    track_budget,
)
from ai_travel_agent.agents.state import TravelState
from ai_travel_agent.agents.supervisor import supervisor_router
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)
_DB_PATH = "data/checkpoints.db"


def _make_checkpointer(db_path: str) -> SqliteSaver:
    import os

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)


def build_graph(db_path: str = _DB_PATH) -> Any:
    builder = StateGraph(TravelState)

    # ── nodes ──────────────────────────────────────────────────────────
    builder.add_node("parse_preferences", parse_preferences)
    builder.add_node("allocate_budget", allocate_budget)  # week 8
    builder.add_node("search_flights", search_flights)
    builder.add_node("search_hotels", search_hotels)
    builder.add_node("find_attractions", find_attractions)
    builder.add_node("find_restaurants", find_restaurants)
    builder.add_node("check_weather", check_weather)
    builder.add_node("track_budget", track_budget)
    builder.add_node("build_geo_clusters", build_geo_clusters)
    builder.add_node("build_itinerary", build_itinerary)  # ← new
    builder.add_node("evaluate_budget", evaluate_budget)  # week 8
    builder.add_node("assemble_output", assemble_output)
    builder.add_node("handle_error", handle_error)

    # ── entry ──────────────────────────────────────────────────────────
    builder.add_conditional_edges(
        START,
        supervisor_router,
        {
            "parse_preferences": "parse_preferences",
            "search_flights": "search_flights",
            "handle_error": "handle_error",
        },
    )

    # ── parse → search ─────────────────────────────────────────────────
    builder.add_conditional_edges(
        "parse_preferences",
        supervisor_router,
        # {"search_flights": "search_flights", "handle_error": "handle_error"},
        {"search_flights": "allocate_budget", "handle_error": "handle_error"},  # week 8
    )

    # ── sequential search chain ────────────────────────────────────────
    builder.add_edge("search_flights", "search_hotels")
    builder.add_edge("search_hotels", "find_attractions")
    builder.add_edge("find_attractions", "find_restaurants")
    builder.add_edge("find_restaurants", "check_weather")
    builder.add_edge("allocate_budget", "search_flights")  # week 8

    # ── search → budget → build → assemble ────────────────────────────
    builder.add_edge("check_weather", "track_budget")
    # week 8 ,9
    # builder.add_edge("track_budget", "build_itinerary")
    builder.add_edge("track_budget", "build_geo_clusters")  # week 9
    builder.add_edge("build_geo_clusters", "build_itinerary")  # week 9
    builder.add_edge("build_itinerary", "evaluate_budget")
    builder.add_edge("evaluate_budget", "assemble_output")

    # builder.add_edge("track_budget", "build_itinerary")  # ← new
    # builder.add_edge("build_itinerary", "assemble_output")  # ← new

    # ── terminal ───────────────────────────────────────────────────────
    builder.add_edge("assemble_output", END)
    builder.add_edge("handle_error", END)

    checkpointer = _make_checkpointer(db_path)
    compiled = builder.compile(checkpointer=checkpointer)
    logger.info("Graph compiled — %d nodes (Week 5)", len(builder.nodes))
    return compiled


agent = build_graph()
