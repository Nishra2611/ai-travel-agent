"""Unit tests for the supervisor router — no LLM, no tools called."""

from langgraph.graph import END

from ai_travel_agent.agents.state import TravelState
from ai_travel_agent.agents.supervisor import supervisor_router


def make_state(status: str) -> TravelState:
    return {"status": status, "raw_input": "test", "messages": []}


def test_routes_parse() -> None:
    assert supervisor_router(make_state("parse")) == "parse_preferences"


def test_routes_search() -> None:
    assert supervisor_router(make_state("search")) == "search_flights"


def test_routes_budget() -> None:
    assert supervisor_router(make_state("budget")) == "track_budget"


def test_routes_assemble() -> None:
    assert supervisor_router(make_state("assemble")) == "assemble_output"


def test_routes_error() -> None:
    assert supervisor_router(make_state("error")) == "handle_error"


def test_routes_done_returns_end() -> None:
    result = supervisor_router(make_state("done"))
    assert result == END


def test_unknown_status_routes_to_error() -> None:
    result = supervisor_router(make_state("totally_unknown_status"))
    assert result == "handle_error"


def test_missing_status_routes_to_error() -> None:
    state: TravelState = {"raw_input": "test", "messages": []}
    result = supervisor_router(state)
    assert result == "handle_error"
