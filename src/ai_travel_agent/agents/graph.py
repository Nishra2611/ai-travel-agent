"""
ai_travel_agent/agents/graph.py

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
"""

from __future__ import annotations

import sqlite3
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from ai_travel_agent.agents.nodes import (
    assemble_output,
    check_weather,
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

# SQLite DB path — relative to project root
_DB_PATH = "data/checkpoints.db"


def _make_checkpointer(db_path: str = _DB_PATH) -> SqliteSaver:
    """Create (or reuse) a SQLite checkpointer."""
    import os

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)


def build_graph(db_path: str = _DB_PATH) -> Any:
    """
    Build, compile, and return the compiled LangGraph agent.

    Parameters
    ----------
    db_path : str
        Path to the SQLite file used for session checkpointing.
        Defaults to data/checkpoints.db in the project root.

    Returns
    -------
    CompiledStateGraph  (LangGraph compiled graph object)
    """
    builder = StateGraph(TravelState)

    # ── register nodes ──────────────────────────────────────────────────
    builder.add_node("parse_preferences", parse_preferences)
    builder.add_node("search_flights", search_flights)
    builder.add_node("search_hotels", search_hotels)
    builder.add_node("find_attractions", find_attractions)
    builder.add_node("find_restaurants", find_restaurants)
    builder.add_node("check_weather", check_weather)
    builder.add_node("track_budget", track_budget)
    builder.add_node("assemble_output", assemble_output)
    builder.add_node("handle_error", handle_error)

    # ── entry edge ───────────────────────────────────────────────────────
    # START → supervisor decides first node based on initial status
    builder.add_conditional_edges(
        START,
        supervisor_router,
        {
            "parse_preferences": "parse_preferences",
            "search_flights": "search_flights",
            "handle_error": "handle_error",
        },
    )

    # ── after parse → supervisor routes to search ─────────────────────
    builder.add_conditional_edges(
        "parse_preferences",
        supervisor_router,
        {
            "search_flights": "search_flights",
            "handle_error": "handle_error",
        },
    )

    # ── parallel search fan-out ──────────────────────────────────────
    # All four search nodes + weather run independently.
    # Each one finishes and writes its slice of state.
    # After ALL finish, we manually set status="budget" in each node
    # by chaining them sequentially here (true parallelism comes in Week 9).
    # For Week 4: sequential chain, same result, simpler to debug.
    builder.add_edge("search_flights", "search_hotels")
    builder.add_edge("search_hotels", "find_attractions")
    builder.add_edge("find_attractions", "find_restaurants")
    builder.add_edge("find_restaurants", "check_weather")

    # ── after all search nodes → budget ─────────────────────────────
    builder.add_edge("check_weather", "track_budget")

    # ── after budget → assemble ──────────────────────────────────────
    builder.add_edge("track_budget", "assemble_output")

    # ── terminal edges ───────────────────────────────────────────────
    builder.add_edge("assemble_output", END)
    builder.add_edge("handle_error", END)

    # ── compile with SQLite checkpointer ─────────────────────────────
    checkpointer = _make_checkpointer(db_path)
    compiled = builder.compile(checkpointer=checkpointer)

    logger.info("LangGraph agent compiled — nodes: %d", len(builder.nodes))
    return compiled


# Module-level singleton — imported by API and scripts
agent = build_graph()
