"""
ai_travel_agent/agents/supervisor.py

Deterministic supervisor — reads state.status and returns the name of
the next node to execute. No LLM call here. This is intentional for Week 4:
a reliable rule-based router is faster to test, easier to debug, and
gives us a stable baseline before we add an LLM-based router in Week 10.

Routing table:
  status="parse"    → "parse_preferences"
  status="search"   → "search_flights"   (first of the parallel search nodes)
  status="budget"   → "track_budget"
  status="assemble" → "assemble_output"
  status="error"    → "handle_error"
  status="done"     → END
  anything else     → "handle_error"
"""

from __future__ import annotations

from langgraph.graph import END

from ai_travel_agent.agents.state import TravelState
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

# Maps status strings to node names
_ROUTING_TABLE: dict[str, str] = {
    "parse": "parse_preferences",
    "search": "search_flights",
    "budget": "track_budget",
    "assemble": "assemble_output",
    "error": "handle_error",
}


def supervisor_router(state: TravelState) -> str:
    """
    LangGraph conditional edge function.
    Returns a node name (str) or END sentinel.
    Called by LangGraph after every node that connects via add_conditional_edges.
    """
    status = state.get("status", "error")
    logger.info("supervisor_router: status=%r", status)

    if status == "done":
        return END

    next_node = _ROUTING_TABLE.get(status)
    if next_node is None:
        logger.warning("supervisor_router: unknown status=%r → handle_error", status)
        return "handle_error"

    return next_node
