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
    generate_map,
    generate_pdf,
    handle_error,
    optimize_routes,
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
    builder.add_node("allocate_budget", allocate_budget)
    builder.add_node("search_flights", search_flights)
    builder.add_node("search_hotels", search_hotels)
    builder.add_node("find_attractions", find_attractions)
    builder.add_node("find_restaurants", find_restaurants)
    builder.add_node("check_weather", check_weather)
    builder.add_node("track_budget", track_budget)
    builder.add_node("build_geo_clusters", build_geo_clusters)
    builder.add_node("build_itinerary", build_itinerary)
    builder.add_node("optimize_routes", optimize_routes)
    builder.add_node("evaluate_budget", evaluate_budget)
    builder.add_node("assemble_output", assemble_output)
    builder.add_node("generate_map", generate_map)
    builder.add_node("generate_pdf", generate_pdf)  # ← new
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

    # ── parse → allocate → search ─────────────────────────────────────
    builder.add_conditional_edges(
        "parse_preferences",
        supervisor_router,
        {"search_flights": "allocate_budget", "handle_error": "handle_error"},
    )
    builder.add_edge("allocate_budget", "search_flights")

    # ── sequential search chain ────────────────────────────────────────
    builder.add_edge("search_flights", "search_hotels")
    builder.add_edge("search_hotels", "find_attractions")
    builder.add_edge("find_attractions", "find_restaurants")
    builder.add_edge("find_restaurants", "check_weather")

    # ── search → budget → geo → build → optimize → evaluate → assemble → map → pdf ─
    builder.add_edge("check_weather", "track_budget")
    builder.add_edge("track_budget", "build_geo_clusters")
    builder.add_edge("build_geo_clusters", "build_itinerary")
    builder.add_edge("build_itinerary", "optimize_routes")
    builder.add_edge("optimize_routes", "evaluate_budget")
    builder.add_edge("evaluate_budget", "assemble_output")
    builder.add_edge("assemble_output", "generate_map")
    builder.add_edge("generate_map", "generate_pdf")  # ← new

    # ── terminal ───────────────────────────────────────────────────────
    builder.add_edge("generate_pdf", END)  # ← changed from generate_map
    builder.add_edge("handle_error", END)

    checkpointer = _make_checkpointer(db_path)
    compiled = builder.compile(checkpointer=checkpointer)
    logger.info("Graph compiled — %d nodes (Week 14)", len(builder.nodes))
    return compiled


agent = build_graph()
# """
# Builds and compiles the LangGraph StateGraph.

# Graph topology:
#   START
#     ↓
#   [supervisor_router]  ← conditional edge after every tool node
#     ↓ "parse"
#   parse_preferences
#     ↓ (sets status="search")
#   [supervisor_router]
#     ↓ "search"
#   search_flights  ──┐
#   search_hotels   ──┤  sequential chain
#   find_attractions──┤
#   find_restaurants──┤
#   check_weather   ──┘
#     ↓ all complete → status="budget"
#   [supervisor_router]
#     ↓ "budget"
#   track_budget
#     ↓ status="assemble"
#   assemble_output
#     ↓ status="done"
#   END

# The SQLite checkpointer gives every session a thread_id so conversation
# history and tool results persist across multiple HTTP requests.

# Usage:
#     from ai_travel_agent.agents.graph import build_graph
#     graph = build_graph()
#     result = graph.invoke(
#         {"raw_input": "Paris 5 days $3000", "status": "parse", "messages": []},
#         config={"configurable": {"thread_id": "session-abc"}},
#     )
# """

# from __future__ import annotations

# import sqlite3
# from typing import Any

# from langgraph.checkpoint.sqlite import SqliteSaver
# from langgraph.graph import END, START, StateGraph

# from ai_travel_agent.agents.nodes import (
#     allocate_budget,
#     assemble_output,
#     build_geo_clusters,
#     build_itinerary,
#     check_weather,
#     evaluate_budget,
#     find_attractions,
#     find_restaurants,
#     handle_error,
#     optimize_routes,
#     parse_preferences,
#     search_flights,
#     search_hotels,
#     track_budget,
#     generate_map,
# )
# from ai_travel_agent.agents.state import TravelState
# from ai_travel_agent.agents.supervisor import supervisor_router
# from ai_travel_agent.utils.logger import get_logger

# logger = get_logger(__name__)
# _DB_PATH = "data/checkpoints.db"


# def _make_checkpointer(db_path: str) -> SqliteSaver:
#     import os

#     os.makedirs(os.path.dirname(db_path), exist_ok=True)
#     conn = sqlite3.connect(db_path, check_same_thread=False)
#     return SqliteSaver(conn)


# def build_graph(db_path: str = _DB_PATH) -> Any:
#     builder = StateGraph(TravelState)

#     builder.add_node("parse_preferences", parse_preferences)
#     builder.add_node("allocate_budget", allocate_budget)
#     builder.add_node("search_flights", search_flights)
#     builder.add_node("search_hotels", search_hotels)
#     builder.add_node("find_attractions", find_attractions)
#     builder.add_node("find_restaurants", find_restaurants)
#     builder.add_node("check_weather", check_weather)
#     builder.add_node("track_budget", track_budget)
#     builder.add_node("build_geo_clusters", build_geo_clusters)
#     builder.add_node("build_itinerary", build_itinerary)
#     builder.add_node("evaluate_budget", evaluate_budget)
#     builder.add_node("optimize_routes", optimize_routes)
#     builder.add_node("assemble_output", assemble_output)
#     builder.add_node("generate_map",generate_map)
#     builder.add_node("handle_error", handle_error)

#     # entry
#     builder.add_conditional_edges(
#         START,
#         supervisor_router,
#         {
#             "parse_preferences": "parse_preferences",
#             "search_flights": "search_flights",
#             "handle_error": "handle_error",
#         },
#     )

#     # parse → allocate_budget → search chain
#     builder.add_conditional_edges(
#         "parse_preferences",
#         supervisor_router,
#         {"search_flights": "allocate_budget", "handle_error": "handle_error"},
#     )
#     builder.add_edge("allocate_budget", "search_flights")
#     builder.add_edge("search_flights", "search_hotels")
#     builder.add_edge("search_hotels", "find_attractions")
#     builder.add_edge("find_attractions", "find_restaurants")
#     builder.add_edge("find_restaurants", "check_weather")

#     # search → budget → geo → build → optimize → evaluate → assemble
#     builder.add_edge("check_weather", "track_budget")
#     builder.add_edge("track_budget", "build_geo_clusters")
#     builder.add_edge("build_geo_clusters", "build_itinerary")
#     builder.add_edge("build_itinerary", "optimize_routes")
#     builder.add_edge("optimize_routes", "evaluate_budget")
#     # builder.add_edge("evaluate_budget", "assemble_output")

#     # # terminal
#     # builder.add_edge("assemble_output", END)
#     builder.add_edge(
#     "evaluate_budget",
#     "assemble_output",)
#     builder.add_edge("assemble_output","generate_map",)
#     builder.add_edge("generate_map",END)
#     builder.add_edge("handle_error", END)

#     checkpointer = _make_checkpointer(db_path)
#     compiled = builder.compile(checkpointer=checkpointer)
#     logger.info("Graph compiled — %d nodes", len(builder.nodes))
#     return compiled


# agent = build_graph()
"""
ai_travel_agent/agents/graph.py — Week 14 update

Adds generate_pdf after generate_map. Builds on the full Week 8-13
pipeline.

New pipeline:
  parse_preferences
    → allocate_budget                              (Week 8)
    → search_flights → search_hotels → find_attractions
    → find_restaurants → check_weather
    → track_budget
    → build_geo_clusters                            (Week 9)
    → build_itinerary
    → optimize_routes                               (Week 10)
    → evaluate_budget                                (Week 8)
    → assemble_output
    → generate_map                                   (Week 13)
    → generate_pdf          ← NEW Week 14 (last node before END)
    → END

generate_pdf runs after generate_map, not before or in parallel, because it
embeds generate_map's thumbnail PNG and links to its HTML map -- a strict
information dependency, same reasoning used for every other node ordering
decision in this pipeline. It's also the last node before END: if PDF
rendering fails (WeasyPrint's system dependencies are the most likely
culprit -- see pdf_generator.py's module docstring), the person still gets
their JSON itinerary and their interactive map, which is why generate_pdf
never raises and instead records status:"failed" in state["pdf_output"]
(see nodes.py).
"""
